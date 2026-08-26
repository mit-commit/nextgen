# Academic-page hunt for the ORCID-only cohort

Round-12 task 7. Population: 141 people whose `links.json` best_tier is `professional` with an ORCID-sourced candidate (close to, but not exactly, the queue's stated 158 -- `links.json` has kept evolving under concurrent sessions; this is the precise, reproducible count as of this run).

**101/141 found** a permanent academic/lab/institutional page (or, for the handful now in industry, their own current first-party site -- the RULING's "best active site" fallback). **40 not found** -- genuinely unresolved (common-name collisions with no disambiguating institution, people with no traceable current page, or people who moved to industry roles with no personal/academic page at all). None were guessed; every hit was cross-checked against paper topic/co-authorship, not name alone.

## Real ORCID/OpenAlex mismatches found (11 people)

Working through this population surfaced a genuine data-quality problem: for 11 people, the ORCID record (or, in 2 cases, the OpenAlex affiliation) that `harvest/authors/enrich_openalex.py` resolved and stored in `enriched.json` describes a **different, wrong person** -- caught by the employment history/field being flatly inconsistent with the actual paper they co-authored with us (e.g. a "Deepak Narayanan" whose OpenAlex affiliation is "Sathyabama Institute" when the real one is an NVIDIA/Stanford ML-systems researcher who co-authored Zaharia:CIDR:2017). For 5 of the 11, the researcher still found the *correct* page via an independent search (name + our own paper context) -- recorded as `found` below, with the mismatch noted in that entry's evidence text. For the other 6, no correct page could be found either, so they stay `not_found`:

- `albert-ma` -- not_found
- `anant-agarwal` -- found (https://www.csail.mit.edu/person/anant-agarwal)
- `andrew-adams` -- found (https://andrew.adams.pub/)
- `deepak-narayanan` -- found (https://deepakn94.github.io/)
- `jason-miller` -- not_found
- `jessica-ray` -- found (https://www.ll.mit.edu/biographies/jessica-ray)
- `mark-halsey` -- not_found
- `martin-c-martin` -- not_found
- `rajeev-barua` -- found (https://ece.umd.edu/clark/faculty/361/Rajeev-Barua)
- `steven-hall` -- not_found
- `yanbin-liu` -- not_found

Recommend a follow-up task: re-run `enrich_openalex.py`'s shared-work verification for these 11 specifically, or manually clear their bad ORCID link in `enriched.json` so a future academic-page/LinkedIn pass doesn't inherit the same wrong steer.

## Found (101)

| person | institution | confidence | url |
|---|---|---|---|
| a-lerer | OpenAI (formerly Meta AI/FAIR) | medium | https://adamlerer.github.io/ |
| ajay-brahmakshatriya | Massachusetts Institute of Technology, CSAIL (PhD student, advised by Saman Amarasinghe) | high | https://www.csail.mit.edu/person/ajay-brahmakshatriya |
| alex-renda | MIT (PhD 2024, advisor Michael Carbin) | high | https://alexrenda.com/ |
| amalee-wilson | Stanford University (PhD student, Computer Science) | high | https://profiles.stanford.edu/amalee-wilson |
| amy-williams | Brigham Young University (Associate Professor) | high | https://hapi-dna.org/lab/ |
| anant-agarwal | Massachusetts Institute of Technology (Professor, CSAIL) | high | https://www.csail.mit.edu/person/anant-agarwal |
| andrew-adams | Adobe Research (Principal Scientist) | high | https://andrew.adams.pub/ |
| andrew-v-pochinsky | MIT Center for Theoretical Physics | high | https://ctp.lns.mit.edu/personnel.html |
| ariya-shajii | Exaloop (Founder) | high | https://ars.me |
| armando-solar-lezama | MIT CSAIL (Distinguished Professor) | high | https://people.csail.mit.edu/asolar/ |
| bonnie-berger | Massachusetts Institute of Technology (Simons Professor of Mathematics, CSAIL) | high | https://people.csail.mit.edu/bab/index.html |
| brian-r-murphy | Stanford SUIF Compiler Group (historical); later Intel | medium | https://suif.stanford.edu/~brm/resume/resume.pdf |
| ce-guo | Imperial College London, Department of Computing (Research Fellow) | high | https://profiles.imperial.ac.uk/c.guo |
| changwan-hong | MIT CSAIL | high | https://www.csail.mit.edu/person/changwan-hong |
| charith-mendis | University of Illinois Urbana-Champaign | high | https://charithmendis.com |
| csaba-andras-moritz | UMass Amherst, Electrical and Computer Engineering | high | https://www.umass.edu/nanofabrics/users/andras/ |
| cy-chan | Lawrence Berkeley National Laboratory (Computer Research Scientist) | high | https://profiles.lbl.gov/20953-cy-chan |
| daniel-sainati | University of Pennsylvania (PLClub, PhD student) | high | https://sainati.pl/ |
| daniel-sanchez | MIT CSAIL (Professor of EECS) | high | https://www.csail.mit.edu/person/daniel-sanchez |
| danny-m-kaufman | Adobe Research | high | https://research.adobe.com/person/danny-kaufman/ |
| david-i-w-levin | University of Toronto (Associate Professor) / NVIDIA (Principal Research Scientist) | high | http://www.diwlevin.com |
| david-wentzlaff | Princeton University (Professor, Electrical and Computer Engineering) | high | https://ece.princeton.edu/people/david-wentzlaff |
| deepak-narayanan | NVIDIA (ADLR group); PhD Stanford, advised by Matei Zaharia | high | https://deepakn94.github.io/ |
| desai-chen | Foundation EGI (2025-present); previously Inkbit (2017-2025) | medium | http://desaic.github.io |
| dustin-richmond | UC Santa Cruz, Baskin School of Engineering | high | https://www.dustinrichmond.com |
| ed-bugnion | École Polytechnique Fédérale de Lausanne (Full Professor, VP for Innovation and Impact) | high | https://people.epfl.ch/edouard.bugnion |
| emanuele-del-sozzo | MIT FutureTech (Research Scientist) | high | https://futuretech.mit.edu/team/emanuele-del-sozzo |
| emma-brunskill | Stanford University (Associate Professor of Computer Science) | high | https://profiles.stanford.edu/emma-brunskill |
| emmett-witchel | University of Texas at Austin (Professor, CS) | high | https://www.cs.utexas.edu/~witchel/ |
| eric-atkinson | Binghamton University (Assistant Professor, since Spring 2024) | high | https://www.binghamton.edu/computer-science/people/profile.html?id=eatkinson2 |
| etienne-vouga | University of Texas at Austin (Associate Professor, CS) | high | https://www.cs.utexas.edu/~evouga/ |
| frederic-vivien | INRIA / Ecole Normale Superieure de Lyon (senior researcher) | high | https://www.ens-lyon.fr/lecole/nous-connaitre/annuaire/frederic-vivien |
| fredrik-kjolstad | Stanford University | high | http://fredrikbk.com |
| gayashan-amarasinghe | University of Moratuwa, Department of Computer Science & Engineering (Senior Lecturer) | medium | https://sites.google.com/a/cse.mrt.ac.lk/dmcse/members/gayashanna |
| gilbert-louis-bernstein | University of Washington, Allen School (Assistant Professor) | high | https://www.cs.washington.edu/people/faculty/gilbert-bernstein/ |
| gurtej-kanwar | University of Edinburgh, School of Physics and Astronomy | high | https://www.ph.ed.ac.uk/people/gurtej-kanwar |
| haojie-ye | NVIDIA (Computer Architecture); PhD University of Michigan (advised by Trevor Mudge) | high | https://linestro.github.io/ |
| haris-smajlovic | Yale University (Postdoctoral Associate) | high | https://harissmajlovic.com |
| hongxiang-fan | Imperial College London, Department of Computing | high | https://profiles.imperial.ac.uk/hongxiang.fan |
| ibrahim-numanagic | University of Victoria, Dept. of Computer Science | high | https://www.uvic.ca/ecs/computerscience/people/faculty/profiles/numanagi%C4%87-ibrahim.php |
| ilya-sergey | National University of Singapore (Associate Professor) | high | http://ilyasergey.net |
| j-bachrach | University of California, Berkeley (Adjunct Assistant Professor, EECS) | high | https://www2.eecs.berkeley.edu/Faculty/Homepages/bachrach.html |
| jaeyeon-won | MIT CSAIL (PhD, co-advised by Saman Amarasinghe and Joel Emer) | high | https://www.csail.mit.edu/person/jaeyeon-won |
| james-j-thomas | Stanford University (PhD student, advised in part by Matei Zaharia) | high | https://cs.stanford.edu/~jjthomas/ |
| james-psota | MIT CSAIL (alumnus) | medium | http://people.csail.mit.edu/jim/index.html |
| jason-ansel | Meta (PyTorch compilers -- TorchDynamo/TorchInductor) | high | https://jasonansel.com/ |
| jessica-ray | MIT Lincoln Laboratory (Cyber Operations and Analysis Technology Group) | high | https://www.ll.mit.edu/biographies/jessica-ray |
| joshua-b-tenenbaum | MIT Brain and Cognitive Sciences (Professor) | high | https://bcs.mit.edu/directory/joshua-b-tenenbaum |
| juan-c-reyes | Escuela Politécnica Nacional (Ecuador), MODEMAT (Founding Director) | high | https://modemat.epn.edu.ec/es/personal/jreyes |
| julian-shun | MIT CSAIL (Associate Professor) | high | https://jshun.csail.mit.edu/ |
| justin-gottschlich | Merly, Inc. (Founder/CEO); formerly Intel Labs / UPenn adjunct | high | http://justingottschlich.com |
| kemal-ebcioglu | Global Supercomputing Corporation (President, since 2006) | high | http://global-supercomputing.com/people/kemal.ebcioglu/bio.html |
| kunle-olukotun | Stanford University, EE/CS | high | https://engineering.stanford.edu/people/oyekunle-olukotun |
| kyle-deeds | Boston University, Computer Science (incoming Assistant Professor) | high | https://www.bu.edu/cs/profiles/kyle-deeds/ |
| maciej-pacula | Independent (bioinformatics/cancer-sequencing industry); formerly MIT | medium | https://mpacula.com/ |
| manya-bansal | Massachusetts Institute of Technology, CSAIL (PhD student, advised by Saman Amarasinghe and Jonathan Ragan-Kelley) | high | https://www.csail.mit.edu/person/manya-bansal |
| manya-ghobadi | MIT CSAIL / EECS | high | https://people.csail.mit.edu/ghobadi/ |
| marc-illa | Pacific Northwest National Laboratory (current); UW physics institute profile (from his 2021-2025 postdoc) | medium | https://iqus.uw.edu/person/1001 |
| marco-d-santambrogio | Politecnico di Milano (Associate Professor, DEIB) | medium | https://www.deib.polimi.it/eng/people/details/356156 |
| mark-stephenson | NVIDIA (Principal Research Scientist) | medium | https://sites.google.com/site/markwstephenson/home |
| martin-hirzel | IBM Research, T.J. Watson Research Center | high | http://hirzels.com/martin/ |
| martin-rinard | MIT CSAIL | high | https://people.csail.mit.edu/rinard/ |
| mary-w-hall | University of Utah, Kahlert School of Computing (Director) | high | https://users.cs.utah.edu/~mhall/ |
| michael-carbin | Massachusetts Institute of Technology (Associate Professor, Head of Programming Systems Group) | high | https://people.csail.mit.edu/mcarbin/ |
| michael-d-ernst | University of Washington, Paul G. Allen School of CSE | high | https://homes.cs.washington.edu/~mernst/ |
| michael-l-wagman | Fermi National Accelerator Laboratory (lattice QCD physicist) | high | https://sites.google.com/view/mwagman/home |
| michael-taylor | University of Washington (Professor) | high | https://www.cs.washington.edu/people/faculty/michael-taylor/ |
| monica-s-lam | Stanford University | high | https://suif.stanford.edu/~lam/ |
| nishil-talathi | University of Illinois Urbana-Champaign (Assistant Professor) | high | https://sites.google.com/site/nishiltalatipersonal/ |
| olivia-hsu | Stanford University | high | https://cs.stanford.edu/~owhsu |
| p-thaker | Stanford University (now VMware Research) | high | https://cs.stanford.edu/~prthaker/ |
| phiala-e-shanahan | MIT Physics (Professor) | high | https://physics.mit.edu/faculty/phiala-shanahan/ |
| philippos-papaphilippou | University of Southampton, Electrical and Electronic Engineering | high | https://www.southampton.ac.uk/people/6688sv/doctor-philippos-papaphilippou |
| phitchaya-mangpo-phothilimthana | OpenAI (previously Google DeepMind/Brain) | high | http://mangpo.net |
| qiyuan-zhao | National University of Singapore (PhD student, VERSE lab) | high | http://zqy1018.top |
| rajeev-barua | University of Maryland, Electrical and Computer Engineering (Professor) | high | https://ece.umd.edu/clark/faculty/361/Rajeev-Barua |
| rastislav-bodik | University of Washington, Allen School (Professor) | high | https://homes.cs.washington.edu/~bodik/ |
| robert-grimm | Formerly NYU CS Associate Professor; now a research scientist at Charles University, Prague | high | https://apparebit.com |
| robert-soule | Yale University (Associate Professor) | high | http://www.cs.yale.edu/homes/soule/ |
| rohan-yadav | Anthropic (Member of Technical Staff; formerly Stanford PhD) | high | https://rohany.github.io/ |
| ryan-senanayake | Reservoir Labs | medium | http://www.rsenapps.com/ |
| sanath-jayasena | University of Moratuwa, Sri Lanka | high | https://uom.lk/staff/Jayasena.VSD |
| shoaib-kamil | Adobe Research | high | https://research.adobe.com/person/shoaib-kamil/ |
| srinivas-devadas | MIT CSAIL / EECS | high | https://www.csail.mit.edu/person/srini-devadas |
| stephen-chou | Google (personal homepage documents his MIT/TACO research background) | high | http://stephenchou.net |
| sunimal-rathnayake | University of Moratuwa, Dept. of Computer Science and Engineering | high | https://sunimalr.staff.uom.lk/ |
| teodora-fields-collin | MIT CSAIL (COMMIT group) | high | https://people.csail.mit.edu/teoc/ |
| una-may-o-reilly | MIT CSAIL (Senior Research Scientist, leader of ALFA Group) | high | https://www.csail.mit.edu/person/una-may-oreilly |
| victor-ying | MIT CSAIL (PhD; transitioning to Tenstorrent) | high | https://victorying.com/ |
| vivek-sarkar | Georgia Tech College of Computing (Dean) | high | https://www.cc.gatech.edu/people/vivek-sarkar |
| vladimir-gladshtein | National University of Singapore (PhD student, School of Computing) | high | https://volodeyka.github.io/ |
| weng-fai-wong | National University of Singapore (Associate Professor, CS) | high | http://www.comp.nus.edu.sg/~wongwf/ |
| william-detmold | MIT, Department of Physics | high | https://physics.mit.edu/faculty/william-detmold/ |
| william-thies | Everwell Health Solutions (co-founder/chair; MIT PhD 2009, StreamIt) | high | https://billthies.net/ |
| willow-ahrens | Georgia Institute of Technology, School of Computer Science (Assistant Professor) | high | https://scs.gatech.edu/people/willow-ahrens |
| wojciech-matusik | MIT (EECS/Mechanical Engineering, CSAIL) | high | https://www.csail.mit.edu/person/wojciech-matusik |
| xipeng-shen | North Carolina State University (Professor) | medium | https://pictureresearch.github.io/picture_website/xshen5/index.htm |
| yewen-pu | Nanyang Technological University, College of Computing and Data Science | high | https://dr.ntu.edu.sg/entities/person/Yewen-Pu |
| yufei-ding | UC San Diego, Computer Science & Engineering | high | https://cse.ucsd.edu/people/faculty-profiles/yufei-ding |
| yunming-zhang | Massachusetts Institute of Technology (PhD, advised by Saman Amarasinghe and Julian Shun) | high | https://yunmingzhang17.github.io/ |
| zohreh-davoudi | University of Maryland, Department of Physics | high | https://umdphysics.umd.edu/people/faculty/current/item/927-davoudi.html |

## Not found (40)

- `albert-ma`: LIKELY WRONG ORCID MATCH: ORCID shows Hefei University of Technology (China) with no dates; our paper is a 2002 MIT Raw-architecture paper. No plausible continuity -- flagging as a probable collision, not accepted.
- `alexander-t-leighton`: Confirmed as Brandeis Math PhD student (matches seq-nature-biotech co-authorship plausibly), but no institutional/personal page found beyond LinkedIn.
- `amina-selma-haichour`: Confirmed real person at ESI Algiers (matches tiramisu-li) but no dedicated homepage, only ResearchGate/conference profiles.
- `andrew-lee`: Confirmed the BMC Bioinformatics 2007 paper context matches (thies:bmc:2007), but the name is too common to isolate a specific personal page for this particular co-author.
- `chris-rinard`: Confirmed as the real NetBlocks co-author, now a software engineer/entrepreneur (Co-Founder, Standard Kernel Co.) -- but no permanent ACADEMIC page found, only a startup-directory aggregator profile (getprog.ai), which doesn't meet the 'faculty/lab/institutional' bar.
- `chris-s-wilson`: openalex_affiliation (Flinders Medical Centre, Australia), authors_latest_affiliation (Stanford), and ORCID employment (PhD Fellow, University of Oslo, 2016-) are mutually inconsistent and none fit our 1994-1996 compiler papers -- a name-collision across multiple wrong 'Chris Wilson' identities, not resolved.
- `christopher-rhodes`: Co-authorship on the 2006 microfluidics paper confirmed via the Hatsopoulos Microfluids Lab's own publication list, but no personal page found (old web.mit.edu student page is 404); openalex 'Texas State University' hit is unverified and not pursued given no corroborating page exists to confirm identity.
- `dai-cheol-jung`: Confirmed real UW ECE PhD (Computer Architecture/VLSI, matches ugcf-isca21), but no personal/lab page found beyond Google Scholar and LinkedIn.
- `daniel-donenfeld`: MIT CSAIL grad student (thesis/papers confirmed by search) but no dedicated personal homepage found, only a thesis PDF and news mentions.
- `devabhaktuni-srikrishna`: Now runs a patient-advocacy company, not academia -- no permanent academic page exists.
- `dillon-sharlet`: Google engineer; only corporate/aggregator profiles, no personal academic page.
- `evelyn-duesterwald`: IBM Research Staff Member/Manager; IBM does not appear to publish a findable individual bio page -- only directory/conference/LinkedIn hits.
- `gregory-sullivan`: WebFetched his old MIT CSAIL frameset page directly -- stale, doesn't reflect his known later moves (BAE, then Draper 2022) -- not accepted as current.
- `guoyu-li`: No page found under 'Guoyu Li' specifically at Imperial College London -- searches surfaced a different person ('Guo Li'). Paper (li:fccm:2026) is too recent/obscure to find a dedicated page.
- `haley-greenyer`: Only an academia.edu profile found (not a permanent institutional page); real person confirmed (co-author on the Seq/seq-nature-biotech paper) but no qualifying page.
- `haoran-xu`: Identity confirmed via the Cimple/PACT18 paper (co-authored with Kiriansky, Rinard, Amarasinghe -- exactly our kiriansky-pact18-cimple paper) but no personal or current institutional page found.
- `ioana-cutcutache`: Now Head of Clinical Bioinformatics at UCB Pharma; no permanent academic page survives from her NUS days, only directory/LinkedIn/ResearchGate hits.
- `jang-kim`: 1997-era MIT LCS Raw-architecture paper co-author; no live page or disambiguating info found -- too old/obscure to trace.
- `jason-kim`: ORCID shows UPenn/Cornell postdoc (recent); our papers are MIT Raw-architecture 2002-2004. No continuity -- likely a common-name collision, not pursued.
- `jason-miller`: Common name; searches only surface the Raw-microprocessor-era MIT papers themselves, no personal/faculty page. ORCID's 'US Naval Research Laboratory since 1986' does not match any search result and may be a mismatched ORCID (same risk pattern as jessica-ray below) -- do not trust that employment field.
- `jeffrey-bosboom`: Appears to have left academia after his MIT PhD (StreamJIT/StreamIt work) -- his MIT CSAIL page is a stale historical student page, not a current one, and no current employer's academic page exists since he's now in industry. Not accepted per the RULING's 'permanent academic page' bar.
- `jennifer-m-anderson`: Historical identity strongly confirmed (Stanford SUIF compiler group PhD 1997, matches our own 1990s papers exactly), but no current traceable permanent page -- both existing hints (OpenAlex 'National Institutes of Health', authors.json 'Stanford') look unconfirmable/possibly stale for a researcher whose visible trail ends in the late 1990s.
- `jiawen-chen`: Identity confirmed (MIT PhD under Frédo Durand, now Principal Research Scientist at Adobe, computational photography) but no dedicated first-party profile/homepage page was found (only aggregator sites -- Scholar, ResearchGate, OpenReview -- and no page at research.adobe.com specifically for him).
- `katsumi-okuda`: Confirmed real and correctly matched (Mitsubishi Electric researcher + MIT visiting researcher, co-author of AskIt with Amarasinghe), but no personal/institutional profile page found -- only publication listings and a ZoomInfo contact card, neither of which qualifies as a permanent academic page.
- `khadidja-kadem`: Identity well-established (NYU Abu Dhabi/ESI Algiers, co-authors with Baghdadi on loop-interchange/Tiramisu work matching tiramisu-li), but no personal/institutional homepage found beyond LinkedIn and Google Scholar.
- `mark-halsey`: LIKELY WRONG ENRICHMENT: ORCID/OpenAlex resolved to a Flinders University criminologist (Matthew Flinders Professor of Law) -- unrelated field to thies:www:2002 (web/multimedia tech). Do not link; flag enriched.json for review.
- `martin-c-martin`: LIKELY WRONG ORCID MATCH: ORCID shows Indonesian universities (Tarumanagara/Universitas Mahkota Tricom Unggul, 2020-) with no clear link to a 2003 MIT compiler paper -- flagging as a probable collision, not accepted.
- `mengjiao-yang`: openalex_affiliation (Affiliated Hospital of North Sichuan Medical College) has nothing to do with our graphit (MIT graph-DSL) paper -- clear wrong-identity OpenAlex match, not pursued further.
- `patricia-suriana`: Now at Prescient Design/Genentech; only aggregator/social profiles found, no faculty/lab page.
- `paul-johnson`: ORCID shows a JPL Section Manager; our papers are MIT Raw-architecture (taylor:isca:2004/micro:2002/isscc:2003). No continuity found between the two -- likely a common-name collision, not pursued further.
- `radha-patel`: MIT MEng/thesis-stage researcher (Radha:meng-thesis:2024) with no ORCID employment or URL data and no findable independent institutional page distinct from student directory listings -- not pursued further given the search results turned up nothing new.
- `richard-wang`: Multiple different Wangs found at MIT CSAIL (Robert Y. Wang, Peng Wang, a CDO-office Richard Wang) but none clearly tied to the 'cola-dcc' paper -- too ambiguous to pick one, not guessed.
- `s-kim`: Initials-only name, ORCID affiliation (Korea University) conflicts with authors.json's HKUST -- too ambiguous to disambiguate without guessing.
- `steven-hall`: LIKELY WRONG ENRICHMENT: ORCID/OpenAlex resolved to a Marine Aquaculture professor at NC State (William White Distinguished Professor) -- completely unrelated field to the actual thies:mm:2009 co-author (StreamIt compressed-video compiler work, confirmed by search to be a real MIT-affiliated Steven J. Hall). Do not link; flag enriched.json for review.
- `vikram-chandrasekhar`: Confirmed identity (co-authored thies:micro:2007 with William Thies/Saman Amarasinghe) but he is now at Google in industry, per Google Scholar -- no permanent academic page exists to find; his ORCID employment history (Egnyte/Google/Facebook/Microsoft) confirms the industry trajectory, consistent with not_found rather than an oversight.
- `walter-lee`: Confirmed as a real Raw-project researcher at MIT, but the only live 'Walter Lee' pages found are a different person (VT engineering-education professor) -- common name, no page found for the compiler researcher.
- `xinyi-chen`: Genuinely ambiguous common name -- ORCID employment (Hong Kong University of Science and Technology), openalex_affiliation (Shanghai Jiao Tong University), and authors_latest_affiliation (MIT) are inconsistent, and search results surfaced several DIFFERENT Xinyi Chens (ELLIS PhD student in NLP, MIT SuperUROP, databases researcher) with no confirmable link to our og-cgo20 compiler paper. Not resolved rather than guessed.
- `yanbin-liu`: LIKELY WRONG ORCID MATCH: this Yanbin Liu's academic career only starts ~2017 (PhD at UTS), field is few-shot deep learning -- inconsistent with our 2013 HPC/false-sharing paper. Flagging as a probable name collision, not accepting the candidate despite ORCID/OpenAlex agreement.
- `yang-cao`: Genuinely ambiguous common name -- ORCID employment history (UNC Charlotte/Zhejiang/LSU), openalex_affiliation (Henan University of Economic and Law), and authors_latest_affiliation (Imperial College London) are all mutually inconsistent, suggesting multiple different 'Yang Cao's have been conflated. No search found an Imperial College London Yang Cao matching our li:fccm:2026 paper's FPGA/HPC context. Not resolved rather than guessed.
- `ziheng-wang`: Identity is clear (MIT MEng thesis 'Automatic Optimization of Sparse Tensor Algebra Programs,' matches the tony:2020/senanayake2020sparse papers exactly) but no live personal or institutional page found post-graduation -- residue, not a mismatch.
