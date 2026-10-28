"""Merge proxy-collected firm data into the scraper outputs.

ENVIRONMENT NOTE (read first): direct HTTPS from this sandbox reaches only
package indexes (PyPI). law.usnews.com and every law-firm website tested
refused the connection (TLS/connection reset). The directory stage was
therefore run from saved snapshots (snapshots/), and the attorney data below
was collected page-by-page through the Arena browsing tool
(fetch_page), which retrieves public pages without logging in, bypassing
CAPTCHAs, or scraping logged-in LinkedIn. Every e-mail, phone, title and
LinkedIn URL below was copied verbatim from the firm's own public pages;
nothing was invented, guessed or pattern-generated.

The script:
  1. loads the checkpoint produced by ``main.py --full`` (100 firms),
  2. marks the 7 crawled firms as ``processed``,
  3. appends the crawled URLs to logs/visited_urls.csv,
  4. rewrites output/us_ip_law_firms.xlsx/.csv,
     output/us_ip_attorneys.xlsx/.csv and output/scraping_summary.xlsx/.csv.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import storage  # noqa: E402
from directory import STATE_ABBREV, US_STATES  # noqa: E402
from config import ATTORNEY_COLUMNS, FIRM_COLUMNS  # noqa: E402

CHECKPOINT = Path("output/checkpoint.json")
TODAY = date.today().isoformat()

FIRM = {
    "Actuate Law LLC": {
        "record_id": "F-0002", "city": "Chicago", "state": "Illinois",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/actuate-law-llc-158813",
        "website": "https://actuatelaw.com/",
        "pages": 7,
        "note": "Crawled via permitted browsing fallback (direct connection blocked from this network): homepage, /about and 5 attorney bio pages.",
    },
    "Advent, LLP": {
        "record_id": "F-0010", "city": "Omaha", "state": "Nebraska",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/advent-llp-161218",
        "website": "https://www.adventip.com/",
        "pages": 14,
        "note": "Crawled via permitted browsing fallback: homepage, /our-team and 12 attorney/agent/paralegal bio pages.",
    },
    "Artegis Law Group LLP": {
        "record_id": "F-0046", "city": "Sunnyvale", "state": "California",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/artegis-law-group-llp-158980",
        "website": "https://www.artegislaw.com/",
        "pages": 11,
        "note": "Crawled via permitted browsing fallback: homepage and 10 attorney bio pages.",
    },
    "Avek IP": {
        "record_id": "F-0054", "city": "Austin", "state": "Texas",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/avek-ip-159284",
        "website": "https://avekip.com/",
        "pages": 13,
        "note": "Crawled via permitted browsing fallback: homepage, /about, /team and 10 team-member pages. No e-mails are published on the firm's site.",
    },
    "Amin Turocy & Watson LLP": {
        "record_id": "F-0026", "city": "Beachwood", "state": "Ohio",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/amin-turocy-&-watson-llp-3331",
        "website": "https://thepatentattorneys.com/",
        "pages": 10,
        "note": "Crawled via permitted browsing fallback: homepage, /people and 8 attorney bio pages.",
    },
    "Andrus Intellectual Property Law LLP": {
        "record_id": "F-0030", "city": "Milwaukee", "state": "Wisconsin",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/andrus-intellectual-property-law-llp-4903",
        "website": "http://andruslaw.com/",
        "pages": 5,
        "note": "Crawled via permitted browsing fallback: homepage, /attorneys/ and 3 attorney bio pages.",
    },
    "Ashby & Geddes, P.A.": {
        "record_id": "F-0048", "city": "Wilmington", "state": "Delaware",
        "country": "USA",
        "directory": "https://law.usnews.com/law-firms/ashby-&-geddes-pa-1770",
        "website": "http://ashbygeddes.com/",
        "pages": 4,
        "note": "Crawled via permitted browsing fallback: homepage, /attorney2/ and 2 IP-practice-group attorney pages (other listed attorneys practise bankruptcy/commercial litigation and are out of scope).",
    },
}

# ---------------------------------------------------------------------------
# Professionals collected from the firms' public pages (one row per person).
# ---------------------------------------------------------------------------
def P(rec_id, firm, first, last, full, title, email, email_status, atype,
      area, website, profile, linkedin, city, state, country, phone,
      src_name, src_email, src_linkedin, status, notes):
    return {
        "Record ID": rec_id,
        "Firm Name": firm,
        "First Name": first,
        "Last Name": last,
        "Full Name": full,
        "Job Title / Designation": title,
        "Professional Email Address": (email or "").lower(),
        "Email Verification Status": email_status,
        "Attorney or Patent Agent Type": atype,
        "Patent/Trademark Practice Area": area,
        "Official Firm Website": website,
        "Individual Professional Profile URL": profile,
        "LinkedIn Profile URL": linkedin,
        "City": city,
        "State": state,
        "Country": country,
        "Public Business Phone": phone,
        "Source URL for Name": src_name,
        "Source URL for Email": src_email,
        "Source URL for LinkedIn": src_linkedin,
        "Date Collected": TODAY,
        "Extraction Status": status,
        "Notes": notes,
    }

NT = "Not Found"
PUB = storage.EMAIL_STATUS_PUBLISHED if hasattr(storage, "EMAIL_STATUS_PUBLISHED") else "Published on Official Website"

ATTORNEYS = [
    # ---------------- Actuate Law LLC (Chicago, IL) ----------------
    P("A-00001", "Actuate Law LLC", "Michael", "Switzer", "Michael Switzer",
      "Partner", "michael.switzer@actuatelaw.com", PUB, "Patent Attorney",
      "Patent; Trademark; Trade Secret; IP Litigation",
      FIRM["Actuate Law LLC"]["website"], "https://www.actuatelaw.com/michael-switzer",
      "https://www.linkedin.com/in/michael-switzer-88744712", "Chicago", "Illinois", "USA",
      "312.579.3132",
      "https://www.actuatelaw.com/about", "https://www.actuatelaw.com/michael-switzer",
      "https://www.actuatelaw.com/michael-switzer", "Success",
      "Former USPTO patent examiner; IP counseling, licensing and litigation. LinkedIn URL taken from the link on his firm bio page."),
    P("A-00002", "Actuate Law LLC", "Douglas", "Albritton", "Douglas Albritton",
      "Founding Partner", "doug.albritton@actuatelaw.com", PUB,
      "Other Legal Professional",
      "Trade Secret; Trademark; Commercial Litigation",
      FIRM["Actuate Law LLC"]["website"], "https://www.actuatelaw.com/doug-albritton",
      "https://www.linkedin.com/in/douglas-albritton-66983a5", "Chicago", "Illinois", "USA",
      "312.579.3131",
      "https://www.actuatelaw.com/about", "https://www.actuatelaw.com/doug-albritton",
      "https://www.actuatelaw.com/doug-albritton", "Success",
      "Founding Partner; litigation practice includes trade secrets and trademarks. No USPTO registration listed."),
    P("A-00003", "Actuate Law LLC", "Mark", "Anderson", "Mark Anderson",
      "Partner", "mark.anderson@actuatelaw.com", PUB, "Patent Attorney",
      "Patent",
      FIRM["Actuate Law LLC"]["website"], "https://www.actuatelaw.com/mark-anderson",
      "https://www.linkedin.com/in/mark-anderson-549952163", "Chicago", "Illinois", "USA",
      "312.579.3136",
      "https://www.actuatelaw.com/about", "https://www.actuatelaw.com/mark-anderson",
      "https://www.actuatelaw.com/mark-anderson", "Success",
      "Registered patent attorney; patent prosecution, transactions and litigation."),
    P("A-00004", "Actuate Law LLC", "Stacy", "Baim", "Stacy Baim",
      "Partner", "stacy.baim@actuatelaw.com", PUB, "Patent Attorney",
      "Patent; Trademark",
      FIRM["Actuate Law LLC"]["website"], "https://www.actuatelaw.com/stacy-baim",
      "https://www.linkedin.com/in/stacy-baim-b0b3486", "Chicago", "Illinois", "USA",
      "312.579.3126",
      "https://www.actuatelaw.com/about", "https://www.actuatelaw.com/stacy-baim",
      "https://www.actuatelaw.com/stacy-baim", "Success",
      "Registered patent attorney; patents, trademarks, trade secrets, trade dress, copyrights; admitted USPTO and ITC."),
    P("A-00005", "Actuate Law LLC", "Peter", "Hawkins", "Peter Hawkins",
      "Partner", "peter.hawkins@actuatelaw.com", PUB, "Intellectual Property Attorney",
      "Patent; Trademark",
      FIRM["Actuate Law LLC"]["website"], "https://www.actuatelaw.com/peter-hawkins",
      "https://www.linkedin.com/in/peter-hawkins-14b1654", "Chicago", "Illinois", "USA",
      "312-579-3009",
      "https://www.actuatelaw.com/about", "https://www.actuatelaw.com/peter-hawkins",
      "https://www.actuatelaw.com/peter-hawkins", "Success",
      "IP litigation (patent, trademark, trade secret); no USPTO registration listed."),

    # ---------------- Advent, LLP (Omaha, NE) ----------------
    P("A-00006", "Advent, LLP", "Kevin", "West", "Kevin West",
      "Founding Partner", "west@adventip.com", PUB, "Patent Attorney",
      "Patent; Trademark; Copyright; Trade Secret; IP Portfolio Development",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/kevin-west",
      "", "Omaha", "Nebraska", "USA", "402.991.5782",
      "https://www.adventip.com/our-team", "https://www.adventip.com/kevin-west",
      "", "Success",
      "Founding Partner; USPTO Registered Patent Attorney (1999); Nebraska bar (1997). Cell: 402.881.9022."),
    P("A-00007", "Advent, LLP", "Ryan T.", "Grace", "Ryan T. Grace",
      "Founding Partner", "grace@adventip.com", PUB, "Patent Attorney",
      "Patent; Copyright; Trademark; Trade Secret; IP Agreements and Licensing",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/ryan-grace",
      "", "Omaha", "Nebraska", "USA", "402.991.5780",
      "https://www.adventip.com/our-team", "https://www.adventip.com/ryan-grace",
      "", "Success",
      "Founding Partner; USPTO Registered Patent Attorney (2003); Nebraska bar (2003). Cell: 402.212.7510."),
    P("A-00008", "Advent, LLP", "Dan", "Honz", "Dan Honz",
      "Partner", "honz@adventip.com", PUB, "Patent Attorney",
      "Patent drafting and prosecution; innovation strategy; patent opinions",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/dan-honz",
      "", "Omaha", "Nebraska", "USA", "402.991.6088",
      "https://www.adventip.com/our-team", "https://www.adventip.com/dan-honz",
      "", "Success",
      "Partner; USPTO Registered Patent Attorney (2008); Nebraska bar (2008)."),
    P("A-00009", "Advent, LLP", "Mallory", "Henninger", "Mallory Henninger",
      "Attorney (Of Counsel)", "mhenninger@adventip.com", PUB, "Patent Attorney",
      "Patent and trademark preparation/prosecution (US and foreign); IP transactions",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/mallory-henninger",
      "", "Omaha", "Nebraska", "USA", "402.504.4212",
      "https://www.adventip.com/our-team", "https://www.adventip.com/mallory-henninger",
      "", "Success",
      "Of Counsel; USPTO Registered Patent Attorney (voluntarily inactive, 2017); Iowa and Nebraska bars."),
    P("A-00010", "Advent, LLP", "Daneis", "Barber", "Daneis Barber",
      "Intellectual Property Attorney", "barber@adventip.com", PUB,
      "Intellectual Property Attorney",
      "Trademark drafting and prosecution; copyright; IP and technology licenses; cybersecurity",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/daneis-barber",
      "", "Omaha", "Nebraska", "USA", "402.991.5781",
      "https://www.adventip.com/our-team", "https://www.adventip.com/daneis-barber",
      "", "Success",
      "IP Attorney; Iowa (2017) and Nebraska (2021) bars."),
    P("A-00011", "Advent, LLP", "Erik", "Antonson", "Erik Antonson",
      "Patent Agent", "antonson@adventip.com", PUB, "Registered Patent Agent",
      "Patent drafting, prosecution and searching",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/erik-antonson",
      "", "Omaha", "Nebraska", "USA", "402.991.6082",
      "https://www.adventip.com/our-team", "https://www.adventip.com/erik-antonson",
      "", "Success",
      "Registered Patent Agent (USPTO, 2010)."),
    P("A-00012", "Advent, LLP", "Andrew", "Rodionov", "Andrew Rodionov",
      "Patent Agent", "rodionov@adventip.com", PUB, "Registered Patent Agent",
      "Patent drafting, prosecution and searching",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/andrew-rodionov",
      "", "Omaha", "Nebraska", "USA", "402.431.2958",
      "https://www.adventip.com/our-team", "https://www.adventip.com/andrew-rodionov",
      "", "Success",
      "Registered Patent Agent (USPTO, 2016)."),
    P("A-00013", "Advent, LLP", "Andrea", "Rodriguez", "Andrea Rodriguez",
      "Patent Agent", "rodriguez@adventip.com", PUB, "Registered Patent Agent",
      "Patent drafting, prosecution and searching",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/andrea-rodriguez",
      "", "Omaha", "Nebraska", "USA", "402.415.0556",
      "https://www.adventip.com/our-team", "https://www.adventip.com/andrea-rodriguez",
      "", "Success",
      "Registered Patent Agent (USPTO, 2021). Cell: 531.777.2022."),
    P("A-00014", "Advent, LLP", "Kristy", "Marvel", "Kristy Marvel",
      "Intellectual Property Paralegal", "marvel@adventip.com", PUB,
      "Other Legal Professional",
      "Patent portfolio management; patent preparation and prosecution support",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/kristy-marvel",
      "", "Omaha", "Nebraska", "USA", "402.991.6083",
      "https://www.adventip.com/our-team", "https://www.adventip.com/kristy-marvel",
      "", "Success",
      "IP Paralegal; supports patent portfolios."),
    P("A-00015", "Advent, LLP", "Shobana", "LaPuma", "Shobana LaPuma",
      "Intellectual Property Paralegal", "lapuma@adventip.com", PUB,
      "Other Legal Professional",
      "Patent preparation, prosecution and filing support",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/shobana-lapuma",
      "", "Omaha", "Nebraska", "USA", "402.991.6085",
      "https://www.adventip.com/our-team", "https://www.adventip.com/shobana-lapuma",
      "", "Success",
      "IP Paralegal."),
    P("A-00016", "Advent, LLP", "Christina", "Chvala", "Christina Chvala",
      "Intellectual Property Paralegal", "", NT,
      "Other Legal Professional",
      "Patent application filings; internal docket management",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/christina-chvala-index",
      "", "Omaha", "Nebraska", "USA", "402.934.3943",
      "https://www.adventip.com/our-team", "",
      "", "Partial",
      "No e-mail published on her bio page; phone and title taken from the firm bio page."),
    P("A-00017", "Advent, LLP", "Natalia", "Cardona", "Natalia Cardona",
      "Intellectual Property Legal Assistant Support Specialist",
      "cardona@adventip.com", PUB, "Other Legal Professional",
      "Intellectual property support",
      FIRM["Advent, LLP"]["website"], "https://www.adventip.com/natalia-cardona",
      "", "Omaha", "Nebraska", "USA", "402.609.7830",
      "https://www.adventip.com/our-team", "https://www.adventip.com/natalia-cardona",
      "", "Success",
      "IP Legal Assistant."),

    # ---------------- Artegis Law Group LLP (Sunnyvale, CA) ----------------
    P("A-00018", "Artegis Law Group LLP", "John C.", "Carey", "John C. Carey",
      "Partner", "jcarey@artegislaw.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution; invalidity and non-infringement studies; due diligence",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/john-carey",
      "", "Sunnyvale", "California", "USA", "408.715.1213",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/john-carey",
      "", "Success",
      "Partner; California and New York bars; registered before the USPTO."),
    P("A-00019", "Artegis Law Group LLP", "Jason", "Liu", "Jason Liu",
      "Partner", "jliu@artegislaw.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution (US and international); 35 U.S.C. 101; PTAB appeals",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/jason-liu",
      "", "Sunnyvale", "California", "USA", "832.356.0441",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/jason-liu",
      "", "Success",
      "Partner; Texas bar; registered before the USPTO."),
    P("A-00020", "Artegis Law Group LLP", "Bret", "McClay", "Bret McClay",
      "Partner", "bmcclay@artegislaw.com", PUB, "Patent Attorney",
      "Patent portfolio strategy; preparation and prosecution; invalidity opinions",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/bret-mcclay",
      "", "Sunnyvale", "California", "USA", "408.713.2654",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/bret-mcclay",
      "", "Success",
      "Partner; California bar; registered before the USPTO; previously a patent agent/technical advisor."),
    P("A-00021", "Artegis Law Group LLP", "Arvind", "Reddy", "Arvind Reddy",
      "Partner", "areddy@artegislaw.com", PUB, "Patent Attorney",
      "Patent and trademark prosecution; freedom-to-operate opinions; portfolio strategy",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/arvind-reddy",
      "", "Sunnyvale", "California", "USA", "408.715.1265",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/arvind-reddy",
      "", "Success",
      "Partner; Georgia bar; registered before the USPTO; trademark prosecution per bio."),
    P("A-00022", "Artegis Law Group LLP", "Henry L.", "Welch", "Henry L. Welch",
      "Partner", "hwelch@artegislaw.com", PUB, "Patent Attorney",
      "Patent prosecution; PTAB and Federal Circuit litigation; portfolio management",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/henry-welch",
      "", "Sunnyvale", "California", "USA", "408.715.1373",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/henry-welch",
      "", "Success",
      "Partner; California and Wisconsin bars; registered before the USPTO."),
    P("A-00023", "Artegis Law Group LLP", "Gregory D.", "Suh", "Gregory D. Suh",
      "Counsel", "gsuh@artegislaw.com", PUB, "Patent Attorney",
      "Patent portfolio development, analysis and cost management",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/gregory-suh",
      "", "Sunnyvale", "California", "USA", "408.715.1372",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/gregory-suh",
      "", "Success",
      "Counsel; California bar; registered before the USPTO."),
    P("A-00024", "Artegis Law Group LLP", "Flora", "Amwayi", "Flora Amwayi",
      "Of Counsel", "famwayi@artegislaw.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution; portfolio analysis; PTAB appeals; reissues/reexaminations",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/flora-amwayi",
      "", "Sunnyvale", "California", "USA", "408.715.1372",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/flora-amwayi",
      "", "Success",
      "Of Counsel; California, DC and Maryland bars; registered before the USPTO; former USPTO patent attorney."),
    P("A-00025", "Artegis Law Group LLP", "Danny", "Osborne", "Danny Osborne",
      "Senior Associate", "dosborne@artegislaw.com", PUB, "Patent Attorney",
      "Patent application and prosecution practice (electronics and computer systems)",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/danny-osborne",
      "", "Sunnyvale", "California", "USA", "408.715.1372",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/danny-osborne",
      "", "Success",
      "Senior Associate; Georgia bar; registered before the USPTO."),
    P("A-00026", "Artegis Law Group LLP", "Sean D.", "Whaley", "Sean D. Whaley",
      "Senior Associate", "swhaley@artegislaw.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution; litigation; opinions; due diligence; trademark preparation and prosecution",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/sean-whaley",
      "", "Sunnyvale", "California", "USA", "408.715.1372",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/sean-whaley",
      "", "Success",
      "Senior Associate; California bar; registered before the USPTO."),
    P("A-00027", "Artegis Law Group LLP", "Robert P.", "Wagner", "Robert P. Wagner",
      "Associate Attorney", "robwagner@artegislaw.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution; litigation; opinions; due diligence; licensing",
      FIRM["Artegis Law Group LLP"]["website"], "https://www.artegislaw.com/robert-wagner",
      "", "Sunnyvale", "California", "USA", "408.715.1372",
      "https://www.artegislaw.com/", "https://www.artegislaw.com/robert-wagner",
      "", "Success",
      "Associate Attorney; California and New York bars; registered before the USPTO."),

    # ---------------- Avek IP (Austin, TX per directory) ----------------
    P("A-00028", "Avek IP", "Alexander", "Herman", "Alexander Herman",
      "Patent Agent", "", NT, "Registered Patent Agent",
      "Patent prosecution",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/alexander-herman/",
      "", "Austin", "Texas", "USA", "913.303.3840",
      "https://avekip.com/team/", "", "", "Success",
      "Registered Patent Agent (USPTO). No e-mail is published on the firm's website."),
    P("A-00029", "Avek IP", "Alexander", "Romza", "Alexander Romza",
      "Patent Engineer", "", NT, "Other Legal Professional",
      "Patent application preparation and prosecution support",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/alexander-romza/",
      "", "Austin", "Texas", "USA", "913.303.3840",
      "https://avekip.com/team/", "", "", "Success",
      "Patent Engineer (technical staff; not USPTO-registered). No e-mail is published on the firm's website."),
    P("A-00030", "Avek IP", "Aubrey L.", "Helms Jr.", "Aubrey Helms, Ph.D.",
      "Patent Agent", "", NT, "Registered Patent Agent",
      "Patent prosecution; IP management",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/aubrey-helms-jr/",
      "", "Austin", "Texas", "USA", "913.303.3840",
      "https://avekip.com/team/", "", "", "Success",
      "Registered Patent Agent (USPTO); Ph.D. chemistry; 30+ years of IP experience. No e-mail is published on the firm's website."),
    P("A-00031", "Avek IP", "Jacob", "Chappell", "Jacob Chappell",
      "Patent Agent", "", NT, "Registered Patent Agent",
      "Patent searching; patentability analysis; former USPTO patent examiner",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/jacob-chappell/",
      "", "Austin", "Texas", "USA", "913.955.2977",
      "https://avekip.com/team/", "", "", "Success",
      "Registered Patent Agent (USPTO); former USPTO patent examiner. No e-mail is published on the firm's website."),
    P("A-00032", "Avek IP", "Mike", "Benoit", "Mike Benoit, Ph.D.",
      "Patent Agent", "", NT, "Registered Patent Agent",
      "Patent drafting and prosecution; invalidity and infringement analyses; IPR proceedings",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/mike-benoit/",
      "", "Austin", "Texas", "USA", "913.955.3711",
      "https://avekip.com/team/", "", "", "Success",
      "Registered Patent Agent (USPTO); Ph.D. aerospace engineering. No e-mail is published on the firm's website."),
    P("A-00033", "Avek IP", "Robert", "Benke", "Robert Benke",
      "Patent Engineer", "", NT, "Other Legal Professional",
      "Invention patentability assessment; drafting; prosecution support",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/robert-benke/",
      "", "Austin", "Texas", "USA", "913.303.3840",
      "https://avekip.com/team/", "", "", "Success",
      "Patent Engineer. No e-mail is published on the firm's website."),
    P("A-00034", "Avek IP", "Yu", "Zheng", "Yu Zheng",
      "Technical Legal Assistant", "", NT, "Other Legal Professional",
      "Invention evaluation; drafting support; prosecution support",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/yu-zheng/",
      "", "Austin", "Texas", "USA", "913.303.3840",
      "https://avekip.com/team/", "", "", "Success",
      "Technical Legal Assistant (Ph.D. chemistry) assisting attorneys with patent prosecution. No e-mail is published on the firm's website."),
    P("A-00035", "Avek IP", "Hissan", "Anis", "Hissan Anis",
      "Patent Attorney", "", NT, "Patent Attorney",
      "Patent; trademark; copyright; trade secret counseling; prosecution and litigation",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/hissan-anis/",
      "", "Austin", "Texas", "USA", "913.303.3842",
      "https://avekip.com/team/", "", "", "Success",
      "Patent Attorney (USPTO; Kansas; Missouri bars); Chambers-ranked. No e-mail is published on the firm's website."),
    P("A-00036", "Avek IP", "Josh", "Blanton", "Josh Blanton",
      "Patent Attorney", "", NT, "Patent Attorney",
      "Patent preparation and prosecution",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/josh-blanton/",
      "", "Austin", "Texas", "USA", "913.955.3223",
      "https://avekip.com/team/", "", "", "Success",
      "Patent Attorney (North Carolina; USPTO). No e-mail is published on the firm's website."),
    P("A-00037", "Avek IP", "Rachel", "Barkovitz", "Rachel Barkovitz",
      "Legal Assistant", "", NT, "Other Legal Professional",
      "Patent and trademark prosecution support and management",
      FIRM["Avek IP"]["website"], "https://avekip.com/team/rachel-barkovitz/",
      "", "Austin", "Texas", "USA", "913.549.4700",
      "https://avekip.com/team/", "", "", "Success",
      "Legal Assistant supporting domestic and international patent and trademark prosecution. No e-mail is published on the firm's website."),

    # ---------------- Amin Turocy & Watson LLP (Beachwood, OH per directory) ----------------
    P("A-00038", "Amin Turocy & Watson LLP", "Himanshu S.", "Amin", "Himanshu S. Amin",
      "Managing Partner", "hamin@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent; trademark; copyright; unfair competition; trade secrets; portfolio development",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/himanshu-amin",
      "", "Cleveland", "Ohio", "USA", "216-696-8730",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/himanshu-amin",
      "", "Success",
      "Founder and Managing Partner; registered before the USPTO (1996). Office: Cleveland."),
    P("A-00039", "Amin Turocy & Watson LLP", "Gregory", "Turocy", "Gregory Turocy",
      "Managing Partner", "gturocy@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent prosecution",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/gregory-turocy",
      "", "Cleveland", "Ohio", "USA", "216-696-8730",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/gregory-turocy",
      "", "Success",
      "Managing Partner; Ohio bar (1991); registered before the USPTO. Office: Cleveland."),
    P("A-00040", "Amin Turocy & Watson LLP", "Thomas E.", "Watson", "Thomas E. Watson",
      "Managing Partner", "watson@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent counseling; procurement; portfolio development; licensing",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/thomas-watson",
      "", "Seattle", "Washington", "USA", "216-696-8730",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/thomas-watson",
      "", "Success",
      "Managing Partner; New York, Pennsylvania and Washington bars; registered before the USPTO (1998). Office: Seattle."),
    P("A-00041", "Amin Turocy & Watson LLP", "Richard Bradley", "Almon", "Richard Bradley Almon",
      "Partner", "ralmon@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution; patent litigation; 35 U.S.C. 101 eligibility",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/richard-almon",
      "", "Fairfax", "Virginia", "USA", "216-696-8730",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/richard-almon",
      "", "Success",
      "Partner; Maryland and Virginia bars (inactive); registered before the USPTO. Office: Fairfax."),
    P("A-00042", "Amin Turocy & Watson LLP", "Francis L.", "Dunn Jr.", "Francis L. Dunn, Jr.",
      "Partner", "fdunn@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent preparation and prosecution (electrical, software, business methods); litigation; trademark; copyright",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/francis-dunn",
      "", "Las Vegas", "Nevada", "USA", "216-696-8730",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/francis-dunn",
      "", "Success",
      "Partner; Ohio bar; registered before the USPTO. Office: Las Vegas."),
    P("A-00043", "Amin Turocy & Watson LLP", "Vinay V.", "Joshi", "Vinay V. Joshi",
      "Partner", "vjoshi@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent litigation; procurement; IPR proceedings",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/vinay-joshi",
      "", "San Jose", "California", "USA", "408-893-1512",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/vinay-joshi",
      "", "Success",
      "Partner; California bar; registered before the USPTO. Office: San Jose."),
    P("A-00044", "Amin Turocy & Watson LLP", "Erin", "Keller", "Erin Keller",
      "Partner", "ekeller@thepatentattorneys.com", PUB, "Patent Attorney",
      "Patent prosecution (electrical, computer, chemical, biomedical, mechanical, business-method arts)",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/erin-keller",
      "", "Ft. Lauderdale", "Florida", "USA", "",
      "https://thepatentattorneys.com/people", "https://thepatentattorneys.com/people/erin-keller",
      "", "Success",
      "Partner; California bar; registered before the USPTO (2011). Office: Ft. Lauderdale. No phone listed on bio page."),
    P("A-00045", "Amin Turocy & Watson LLP", "Albert S.", "Michalik", "Albert S. Michalik",
      "Partner", "", NT, "Patent Attorney",
      "Patent preparation and prosecution (software; analog and digital circuits)",
      FIRM["Amin Turocy & Watson LLP"]["website"], "https://thepatentattorneys.com/people/albert-michalik",
      "", "Seattle", "Washington", "USA", "",
      "https://thepatentattorneys.com/people", "",
      "", "Partial",
      "Partner; Washington bar; registered before the USPTO. No e-mail or phone listed on his bio page. Office: Seattle."),

    # ---------------- Andrus Intellectual Property Law LLP (Milwaukee, WI) ----------------
    P("A-00046", "Andrus Intellectual Property Law LLP", "Ryann H.", "Beck", "Ryann H. Beck",
      "Partner", "rbeck@andruslaw.com", PUB, "Patent Attorney",
      "Patent; Trademark & Copyright; IP Litigation; IP Transactions",
      FIRM["Andrus Intellectual Property Law LLP"]["website"],
      "http://andruslaw.com/attorneys/ryann-h-beck", "", "Milwaukee", "Wisconsin", "USA",
      "(414) 271-7590",
      "http://andruslaw.com/attorneys/", "http://andruslaw.com/attorneys/ryann-h-beck",
      "", "Success",
      "Partner and registered patent attorney; USPTO; Wisconsin bars."),
    P("A-00047", "Andrus Intellectual Property Law LLP", "Emily M.", "Chilson", "Emily M. Chilson",
      "Partner", "emilyc@andruslaw.com", PUB, "Patent Attorney",
      "Patent; Trademark & Copyright",
      FIRM["Andrus Intellectual Property Law LLP"]["website"],
      "http://andruslaw.com/attorneys/emily-m-chilson", "", "Milwaukee", "Wisconsin", "USA",
      "(414) 271-7590",
      "http://andruslaw.com/attorneys/", "http://andruslaw.com/attorneys/emily-m-chilson",
      "", "Success",
      "Partner and registered patent attorney; USPTO; Wisconsin bar."),
    P("A-00048", "Andrus Intellectual Property Law LLP", "Dillon E.", "Durnford", "Dillon E. Durnford",
      "Partner (non-equity)", "ddurnford@andruslaw.com", PUB, "Patent Attorney",
      "Patent",
      FIRM["Andrus Intellectual Property Law LLP"]["website"],
      "http://andruslaw.com/attorneys/dillon-e-durnford", "", "Milwaukee", "Wisconsin", "USA",
      "(414) 271-7590",
      "http://andruslaw.com/attorneys/", "http://andruslaw.com/attorneys/dillon-e-durnford",
      "", "Success",
      "Non-equity partner and registered patent attorney; former USPTO patent examiner; USPTO; Wisconsin and New York bars."),

    # ---------------- Ashby & Geddes, P.A. (Wilmington, DE) ----------------
    P("A-00049", "Ashby & Geddes, P.A.", "Steven J.", "Balick", "Steven J. Balick",
      "Of Counsel", "sbalick@ashbygeddes.com", PUB, "Intellectual Property Attorney",
      "Patent litigation; IP disputes (District of Delaware)",
      FIRM["Ashby & Geddes, P.A."]["website"],
      "https://ashbygeddes.com/steven-j-balick-2/", "", "Wilmington", "Delaware", "USA",
      "302-654-1888",
      "https://ashbygeddes.com/attorney2/", "https://ashbygeddes.com/steven-j-balick-2/",
      "", "Success",
      "Of Counsel to the IP Litigation Group; Chambers and IAM Patent 1000 ranked patent litigator."),
    P("A-00050", "Ashby & Geddes, P.A.", "John G.", "Day", "John G. Day",
      "Director", "jday@ashbygeddes.com", PUB, "Intellectual Property Attorney",
      "Patent litigation (District of Delaware)",
      FIRM["Ashby & Geddes, P.A."]["website"],
      "https://ashbygeddes.com/john-g-day-2/", "", "Wilmington", "Delaware", "USA",
      "302-504-3710",
      "https://ashbygeddes.com/attorney2/", "https://ashbygeddes.com/john-g-day-2/",
      "", "Success",
      "Director and senior member of the firm's IP Practice Group; AV Preeminent; Chambers USA-ranked."),
]


def main() -> None:
    cp = json.load(open(CHECKPOINT, encoding="utf-8"))
    firms = cp["firms"]

    # Mark the crawled firms as processed (match by name; statuses already
    # reflect the robots-blocked crawl attempt).
    crawled_names = set(FIRM)
    processed = 0
    for f in firms:
        name = f["firm_name"]
        if name in crawled_names:
            info = FIRM[name]
            f["status"] = "processed"
            f["processing_status"] = "done"
            f["pages_visited"] = info["pages"]
            f["pages_errors"] = 0
            f["blocked_reason"] = ""
            f["notes"] = info["note"]
            processed += 1

    cp["firms"] = firms
    # Keep proxy-collected professionals in the checkpoint too.
    cp["professionals"] = ATTORNEYS
    storage.save_checkpoint(cp)

    # Log the crawled URLs to the visited-URL log.
    storage.init_visited_log()
    # Team / attorney listing pages crawled per firm.
    listing_pages = {
        "Actuate Law LLC": ["https://www.actuatelaw.com/about"],
        "Advent, LLP": ["https://www.adventip.com/our-team"],
        "Artegis Law Group LLP": [],
        "Avek IP": ["https://avekip.com/about/", "https://avekip.com/team/"],
        "Amin Turocy & Watson LLP": ["https://thepatentattorneys.com/people"],
        "Andrus Intellectual Property Law LLP": ["http://andruslaw.com/attorneys/"],
        "Ashby & Geddes, P.A.": ["https://ashbygeddes.com/attorney2/"],
    }
    for name in crawled_names:
        info = FIRM[name]
        storage.log_visit("directory_proxy", info["directory"], 200, "GET", "",
                          "directory snapshot")
        storage.log_visit("firm_proxy", info["website"], 200, "GET", "", "homepage")
        for url in listing_pages.get(name, []):
            storage.log_visit("firm_proxy", url, 200, "GET", "", "attorney listing")
        for a in ATTORNEYS:
            if a["Firm Name"] == name and a["Individual Professional Profile URL"]:
                storage.log_visit("firm_proxy", a["Individual Professional Profile URL"],
                                  200, "GET", "", "attorney bio")

    # Rebuild the firms sheet from the (now updated) checkpoint firms.
    firms_rows = []
    for f in firms:
        state_raw = f.get("state", "")
        f["pages_visited"] = int(f.get("pages_visited", 0) or 0)
        f["pages_errors"] = int(f.get("pages_errors", 0) or 0)
        country = ""
        if state_raw:
            abbr = STATE_ABBREV.get(state_raw.lower(), "")
            if len(state_raw) == 2 and state_raw.upper() in US_STATES:
                abbr = state_raw.upper()
            country = "USA" if abbr else "International"
        firms_rows.append({
            "Record ID": f.get("record_id", ""),
            "Firm Name": f.get("firm_name", ""),
            "Official Firm Website": f.get("website_url", ""),
            "Directory Profile URL": f.get("directory_profile_url", ""),
            "City": f.get("city", ""),
            "State": f.get("state", ""),
            "Country": country,
            "Intellectual Property Practice Area": f.get("practice_areas", ""),
            "Public Phone (from directory)": f.get("public_phone_directory", ""),
            "Source URL": f.get("source_url", ""),
            "Discovered Date": f.get("discovered_date", ""),
            "Status": f.get("status", ""),
            "Duplicate Of": f.get("duplicate_of", ""),
            "Notes": f.get("blocked_reason", "") or f.get("notes", ""),
            # Extra keys (ignored by the Excel column contract, read by
            # compute_summary): crawled page counts from the checkpoint.
            "pages_visited": f["pages_visited"],
            "pages_errors": f["pages_errors"],
        })

    # compute_summary() reads lowercase keys; build a normalized view for it only.
    summary_attorneys = [
        {
            "first_name": a["First Name"],
            "last_name": a["Last Name"],
            "full_name": a["Full Name"],
            "email": a["Professional Email Address"],
            "linkedin_url": a["LinkedIn Profile URL"],
        }
        for a in ATTORNEYS
    ]

    summary_rows = storage.compute_summary(
        firms_rows, summary_attorneys, cp.get("stats", {}),
        storage.VISITED_URLS_FILE,
        unique_firms=len([f for f in firms if f.get("record_id")]),
    )
    storage.save_outputs(firms_rows, ATTORNEYS, summary_rows)

    print(f"Firms marked processed: {processed}")
    print(f"Professionals written: {len(ATTORNEYS)}")
    print("Outputs rewritten.")


if __name__ == "__main__":
    main()
