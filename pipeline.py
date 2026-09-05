"""
The scrape-score-summarise pipeline, with no assumptions about where the
result goes.

run.py uses it to build the local HTML dashboard. publish.py uses it to push
the same data to Redis so the website can serve it. Keeping this in one place
means the live site and your local dashboard can never drift apart.
"""

import concurrent.futures as cf
import datetime
import json
import os
import re
import threading

import providers
import numfmt
import rules
import sources
import summarize

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache.json")

_lock = threading.Lock()


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CACHE)


def spread_across_tags(items, n):
    """
    Choose which filings get an AI summary.

    Straight top-N by score hands every slot to whichever tag scores highest
    that day (usually M&A) and leaves results and order wins with none. So we
    go round the tags in turn, taking each tag's best remaining filing.
    """
    buckets = {}
    for a in items:
        buckets.setdefault(a["tag"], []).append(a)

    order = sorted(buckets, key=lambda t: -max(x["score"] for x in buckets[t]))
    chosen, i = [], 0
    while len(chosen) < n and any(buckets.values()):
        tag = order[i % len(order)]
        if buckets[tag]:
            chosen.append(buckets[tag].pop(0))
        i += 1
        if i > len(order) * (n + 5):
            break
    return chosen


def fetch_and_score(start, end, min_score, log=print):
    """Everything up to but not including the AI step."""
    log("Fetching BSE...")
    bse = sources.fetch_bse(start, end, log=log)
    log("Fetching NSE...")
    nse = sources.fetch_nse(start, end, log=log)

    raw = bse + nse

    # The RSS feeds are NOT read here, deliberately.
    #
    # They were, for a few hours on 3 September, as a safety net for anything
    # the APIs failed to return. It worked and it was a mistake. The feeds
    # carry the whole of both exchanges - debt instruments, mutual fund NAVs,
    # commercial paper redemptions, unlisted private companies - and they carry
    # no category at all, so every one of those 228 daily additions arrived as
    # an uncategorised row for the rules to guess at. Company names came
    # through as things like "VPIL-18%-RESET RATE-27-04-". It cluttered the
    # dashboard for no gain, and Ishan asked for it out.
    #
    # The two coverage faults it was meant to insure against are fixed at the
    # source instead, which is the better place: NSE is asked for all five of
    # its lists, and BSE retries a failed page rather than abandoning the day.
    #
    # The feeds are still read by tools/reconcile_feeds.py, which only reports.
    # Nothing it sees reaches the site.
    log(f"Total filings pulled: {len(raw)}")

    kept = []
    for a in raw:
        s, tag = rules.score(a["category"], a["headline"], a.get("critical"))
        a["score"], a["tag"] = s, tag
        if s >= min_score:
            kept.append(a)

    kept = sources.merge(kept)

    def sort_key(a):
        d = sources.parse_dt(a["dt"])
        return (-a["score"], -(d.timestamp() if d else 0))

    kept.sort(key=sort_key)

    for a in kept:
        d = sources.parse_dt(a["dt"])
        a["time"] = d.strftime("%d %b, %H:%M") if d else ""
        a["date"] = d.strftime("%Y-%m-%d") if d else ""

    log(f"Important after filtering: {len(kept)}")
    return raw, kept


# Tags a summary may not impose. Each says "we could not tell" rather than
# naming an event, and a filing that reached the page on the strength of its
# document should not be renamed to one of them by two sentences about it.
WEAK_FROM_SUMMARY = {"Meeting", "Routine", "Other", "Outcome", "Press Release",
                     "Corp Action", "Annual Report"}

# The categories a reader looks at first, and the ones a PDF most often puts a
# filing into by accident - an auditor's profile listing "Merger & Acquisition"
# among its services was enough, once. These have to be corroborated by the
# summary.
DEAL_TAGS = {"Acquisition", "Scheme Of Arrangement", "Open Offer"}

_DEAL_EVIDENCE = re.compile(
    r"acquisi|acquir|merger|amalgamat|de-?merger|slump sale|divest|"
    r"\bstake\b|shareholding|takeover|share purchase|controlling interest|"
    r"sold its|sale of|joint venture|open offer|scheme of arrangement|"
    r"buy(s|ing)? out|hive[- ]off|transfer of[^.]{0,30}(business|undertaking)|"
    # Three real deals were being demoted for wording this did not know.
    # Capital India "is SELLING its RemitX forex assets to Kanji Forex";
    # International Gemological "will CONSOLIDATE CONTROL over IGI Botswana,
    # making it a wholly owned subsidiary"; NLC India "signed an addendum to
    # TRANSFER about 709 MW of renewable assets".
    r"sell(s|ing)?\b|consolidat\w+ control|control over|"
    r"transfer(ring)? (of )?[^.]{0,30}(assets|megawatt|\bmw\b|portfolio)",
    re.I)


def category_from_summary(category, headline, blob, current=None):
    """The category a filing's own words argue for, or None to keep what it has.

    Pulled out of summarise() so the tests exercise the real decision instead
    of a copy of it. The copy is how this went wrong: the tests asserted on
    rules.score_text() alone while production combined it with the headline,
    so a change that was right in one place and wrong in the other passed.
    """
    # A score threshold used to sit here, refusing anything under 55. It was
    # aimed at one real problem - a dividend whose summary mentions the AGM
    # that will approve it was being relabelled "Meeting" - but it also
    # refused every accurate label that happens to score low. Change In
    # Management is 51, so Hexaware's new chief executive stayed under
    # Acquisition through four passes while the rules named it correctly
    # every time. The tags to refuse are the vague ones, not the low-scoring
    # ones. Nothing is lost by relabelling: the SCORE is never changed here,
    # so a filing keeps its place on the page and only gets a truer name.
    _, from_summary = rules.score_text(blob, floor=0)

    # A letter of intent can describe an acquisition, not a customer order.
    # Keep the original acquisition verdict unless the summary also contains
    # real evidence of commercial work, supply, a contract or a tender.
    if (from_summary == "Order"
            and re.search(r"letter of intent|\bloi\b", blob, re.I)
            and re.search(r"acqui|purchas|\bbuy\b|subscrib", blob, re.I)
            and not re.search(r"customer|client|supply|services?|work order|"
                              r"contract (?:won|awarded|received|secured)|"
                              r"project|tender", blob, re.I)):
        from_summary = None

    # Two ways a filing is a meeting notice, and neither may overrule a real
    # event.
    #
    # The first is that the HEADLINE says so - "corrigendum to its 18th Annual
    # General Meeting notice". Then the notice is the subject of the filing,
    # and the resolutions it recites are things the meeting will be ASKED to
    # approve rather than things that have happened. That is how eight AGM
    # notices came to be filed under Pref.
    #
    # The second is that the summary says so AND names no other event at all.
    # Notice and nothing else.
    #
    # What is deliberately NOT enough is the summary merely mentioning a
    # meeting. The first version of this did exactly that, and renamed four
    # dividends "Meeting" - Sunteck Realty's record date, Foseco's approved
    # final dividend - because the summary mentioned the AGM. There the
    # meeting is context and the dividend is the news.
    # "Names no other event" has to mean no SUBSTANTIVE event, not no tag at
    # all. The tags on the refuse list are the ones that say "we could not
    # tell" - Annual Report, Corp Action, Outcome, Press Release - and reading
    # one of those as an event was enough to block the notice test:
    #
    #   Tega Industries    summary: "50th AGM is scheduled for September 24"
    #                      score_text: (28, Annual Report)  -> not empty
    #                      so the notice branch was skipped, Annual Report was
    #                      then refused as too weak, and the filing kept the
    #                      tag its PDF had given it. Dividend.
    #
    # Seven filings under Dividend on 3 September were meeting notices that
    # got there this way, along with several under Pref and Warrants.
    substantive = from_summary and from_summary not in WEAK_FROM_SUMMARY

    # Who moved the shares is not something a summary can overturn.
    #
    # Promoter Buy/Sell and Inter-se Transfer are set from the stake-disclosure
    # category, which is the authoritative record of WHO - the form is filed
    # under SAST precisely to say so. The summary of one reads "Innovative
    # Money Matters Pvt Ltd acquired 55,000 shares of Avonmore Capital",
    # never using the word promoter at all, and scoring that gives Acquisition
    # at 65. Twelve promoter dealings were being relabelled acquisitions on
    # exactly that: a sentence that does not contradict the category, it just
    # does not repeat it.
    if (current in ("Promoter Buy/Sell", "Inter-se Transfer")
            and from_summary in ("Acquisition", "Stake Change")):
        from_summary = None

    # A notice that the BOARD is going to meet is the same mistake one meeting
    # down: it names the thing the board will consider, so it was filed as that
    # thing. Manba Finance's "will hold a board meeting to consider increasing
    # its authorised share capital" came out as Pref; NHC Foods' "board will
    # meet to discuss a possible fund raise" as Warrants. Neither board had met.
    #
    # Checked before the general meeting test and before everything else,
    # because a board notice mentioning the AGM would otherwise become a
    # Meeting - which is nearer, and still not what the filing is.
    # A deal has to be visible in the summary.
    #
    # Acquisition, Scheme Of Arrangement and Open Offer are the categories a
    # reader looks at first, and the ones that arrive from the PDF most often -
    # an attachment need only mention "merger & acquisition" once. When the
    # summary of the same filing contains no deal language at all, there was no
    # deal: Bodhtree's 2035 vision document, Shadowfax's channel partner
    # programme, and Mobavenue winning four Gold awards at an industry event
    # were all sitting under Acquisition.
    #
    # Whatever the summary DID find is used instead, and "Other" when it found
    # nothing - which is honest, and keeps the filing on the site under All
    # rather than on the front page as a deal that never happened.
    if (current in DEAL_TAGS and blob
            and not _DEAL_EVIDENCE.search(blob)):
        return from_summary or "Other"

    if rules.board_meeting_notice(blob):
        return "Board Meeting"

    # When the general meeting is what the filing is ABOUT - a book closure
    # naming it as the purpose, or a summary that opens by scheduling one - it
    # wins over a substantive read. These filings say "for the AGM and
    # dividend" in one breath, so the dividend is always there to be scored,
    # and five of them were sitting under Dividend on 4 September.
    if rules.meeting_is_the_subject(blob):
        return "Meeting"

    # The backstop. An AGM never belongs in another category, so if this is a
    # notice of a general meeting and nothing was actually approved, declared,
    # allotted, received or paid, it is a Meeting - whatever money words the
    # text happens to contain. Filatex India's letter carrying "web links to
    # the 36th AGM notice and a reminder to claim any unclaimed dividends" was
    # published as a Dividend on those two words.
    if rules.meeting_only(category or "", headline or "", blob):
        return "Meeting"

    if rules.meeting_notice(category or "", headline or "", ""):
        from_summary = "Meeting"
    elif not substantive and rules.meeting_notice("", "", blob):
        from_summary = "Meeting"
    elif not substantive:
        from_summary = None

    # retag() still has the last word. It exists for the cases where the words
    # are right but the meaning is inverted - a tax demand and an order win are
    # both "receipt of order".
    return rules.retag(blob) or from_summary


def summarise(kept, provider_list, max_summaries, workers=4, log=print):
    """Read PDFs and summarise a spread of the most important filings."""
    # Everything worth reading gets a summary. There is no second tier - if a
    # filing is good enough to show, it is good enough to explain. The spread
    # only decides the ORDER when a cap is in force; with no cap it is the
    # whole list, best first.
    if not max_summaries or max_summaries >= len(kept):
        todo = sorted(kept, key=lambda a: -a.get("score", 0))
    else:
        todo = spread_across_tags(kept, max_summaries)
    if not provider_list or not todo:
        return []

    cache = load_cache()
    done = [0]
    fail_reason = [""]        # the last error, for the log line at the end

    def work(a):
        if a["id"] in cache:
            a.update(cache[a["id"]])
            with _lock:
                done[0] += 1
                log(f"  [{done[0]}/{len(todo)}] cached  {a['company'][:42]}")
            return

        res = summarize.summarize(a, provider_list)
        if "error" in res:
            a["summary"] = ""
            a["summary_error"] = str(res["error"])[:160]
            a["impact"] = ""
            a["key_numbers"] = []
            a["why_it_matters"] = ""
            note = "FAILED"
            fail_reason[0] = a["summary_error"]
        else:
            a["summary"] = res.get("summary", "")
            a["impact"] = res.get("impact", "")
            a["key_numbers"] = res.get("key_numbers", [])
            a["why_it_matters"] = res.get("why_it_matters", "")
            with _lock:
                cache[a["id"]] = {k: a[k] for k in
                                  ("summary", "impact", "key_numbers",
                                   "why_it_matters", "source_used")}
            note = a.get("source_used", "")
        with _lock:
            done[0] += 1
            log(f"  [{done[0]}/{len(todo)}] {note:<16} {a['company'][:42]}")

    log(f"Reading {len(todo)} PDFs and summarising...")
    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(work, todo))

    # A rate limit or a timeout is not a verdict on the filing, so anything
    # still without a summary goes round again. Two extra passes is enough to
    # clear a transient failure without grinding on a PDF that cannot be read.
    #
    # But only while there is something left to ask. Once every model has hit
    # its daily cap, a retry cannot succeed, and three passes over a few
    # hundred filings is how one run spent 2h17m on a single day and held the
    # schedule for five and a half hours. The run carries on either way and
    # publishes what it has - a missing summary is not a reason to fail.
    for attempt in (1, 2):
        missing = [a for a in todo if not a.get("summary")]
        if not missing:
            break
        left = providers.alive(provider_list)
        if not left:
            log(f"Retry {attempt}: skipped - every model has used up its quota "
                f"for today ({len(missing)} filings left unsummarised)")
            break
        log(f"Retry {attempt}: {len(missing)} filings still need a summary "
            f"({len(left)} models still available)")
        done[0] = 0
        with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            list(ex.map(work, missing))

    still = [a for a in todo if not a.get("summary")]
    if still:
        log(f"  {len(still)} could not be summarised. Last reason: "
            f"{fail_reason[0] or 'unknown'}")
        gone = providers.dead_models()
        if gone:
            log(f"  models out of quota for today: {', '.join(gone)}")
    save_cache(cache)

    # ---------------------------------------------------------------------
    # The category comes from the SUMMARY, not the document.
    #
    # A filing's PDF is not one statement. It is a document containing many
    # sentences about many things, and scoring 4,000 characters of it means
    # any topic word anywhere decides the label. Every wrong category on the
    # site came from a phrase that belonged to a different sentence: an
    # auditor's list of services ("Merger & Acquisition"), a blank SAST form's
    # own options ("rights issue / preferential allotment"), the other side's
    # name in a lawsuit ("Joint Venture of OHL"), a trading-window paragraph,
    # a website breadcrumb. There is no end to that supply, and patching them
    # one at a time never finishes.
    #
    # The summary is two sentences saying what the filing IS, with none of
    # that in it. Measured over the 1,199 filings live on 1 September: 146
    # carried a category their own summary contradicted; scoring the summary
    # instead leaves 5.
    #
    # The score is NOT changed. Importance was already decided, by the rules
    # and the document, and a filing that earned its place keeps it - this
    # only settles what to call it. Filings without a summary keep the tag the
    # rules gave them, which is the only thing available for them anyway.
    # ---------------------------------------------------------------------
    fixed = 0
    for a in todo:
        # The summary and the figures, but NOT why_it_matters.
        #
        # The summary is an account of what the filing says. why_it_matters is
        # commentary about it, and commentary is where the negations live:
        # Mukat Pipes' AGM book-closure carries "a routine administrative
        # update regarding the upcoming AGM and voting eligibility, with no
        # dividend declared for the year". Scoring that matches the word
        # dividend, at 60, and the filing was published as one - on a sentence
        # whose entire point is that there was no dividend.
        #
        # Nothing is lost. Anything why_it_matters names, the summary named
        # first; that is what it is commentary on.
        blob = " ".join([
            a.get("summary") or "",
            " ".join(a.get("key_numbers") or []),
        ]).strip()
        if not blob:
            continue

        # Two things the summary must not be allowed to decide.
        #
        # The three meeting kinds are settled from the category and headline,
        # and they are already right - Investor Meet is 1% wrong, Concall 0%.
        # Their summaries describe what was DISCUSSED on the call, which is
        # usually the quarter's results, so scoring them moved 17 concalls and
        # investor meets into Results.
        if a.get("tag") in rules._MEETING_TAGS:
            continue

        better = category_from_summary(
            a.get("category", ""), a.get("headline", ""), blob, a.get("tag"))

        if better and better != a["tag"]:
            log(f"  relabelled: {a['company'][:36]:<38} "
                f"{a['tag']} -> {better}")
            a["tag"] = better
            fixed += 1

            # A relabel may also PROMOTE, which it could not before.
            #
            # The score used to be left alone here on purpose, so a filing kept
            # its place on the page and only got a truer name. That was right
            # while everything being relabelled was already above the line.
            # It is wrong for a press release: a company files one under the
            # category "Press Release" with the headline "Please refer attached
            # file", which scores 44, and 44 is below the line. Renaming it
            # "Order" and leaving it at 44 puts a Rs 100 crore order win on a
            # page nobody reads. Balaji Telefilms filed on both exchanges on
            # 4 September and appeared on neither.
            #
            # Only upwards, and only to what the new tag is worth. A summary
            # can rescue a filing the headline buried; it can never bury one.
            worth_now = rules.SCORE_FOR_TAG.get(better, 0)
            if worth_now > a.get("score", 0):
                a["score"] = worth_now
    if fixed:
        log(f"  ({fixed} categories taken from the summary rather than the document)")

    return todo


FIELDS = ("id", "exchange", "company", "ticker", "category", "headline", "time",
          "date", "score", "tag", "pdf_url", "page_url", "summary", "impact",
          "key_numbers", "why_it_matters", "mcap", "also_filed", "also_tags")


def to_rows(kept):
    """Trim to the fields the dashboard and the Excel export actually use."""
    # Figures get tidied on the way out rather than at summarising time, so a
    # summary that has been sitting in the cache since before this existed is
    # corrected too, without paying to generate it again.
    return [numfmt.fix_all({k: a.get(k, "") for k in FIELDS}) for a in kept]


def run(days, min_score, max_summaries, provider_list, workers=4, log=print):
    """Full pipeline. Returns (rows, stats)."""
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    today = datetime.datetime.now(ist).date()
    start = today - datetime.timedelta(days=max(0, days))

    raw, kept = fetch_and_score(start, today, min_score, log=log)
    summarise(kept, provider_list, max_summaries, workers=workers, log=log)

    stats = {
        "scanned": len(raw),
        "important": len(kept),
        "summarised": sum(1 for a in kept if a.get("summary")),
        "from": start.isoformat(),
        "to": today.isoformat(),
    }
    return to_rows(kept), stats
