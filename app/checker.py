"""Deterministic British-English placement checker. No AI or neural models."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable

from .lessons import LESSON_BY_CATEGORY

CHECKER_VERSION = "rules-1.0"
FORMULA_VERSION = "kaplan-1.0"
WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")

IRREGULAR = {
    "arise":"arose","awake":"awoke","be":"was/were","bear":"bore","beat":"beat",
    "become":"became","begin":"began","bend":"bent","bite":"bit","blow":"blew",
    "break":"broke","bring":"brought","build":"built","buy":"bought","catch":"caught",
    "choose":"chose","come":"came","cost":"cost","cut":"cut","deal":"dealt",
    "dig":"dug","do":"did","draw":"drew","drink":"drank","drive":"drove",
    "eat":"ate","fall":"fell","feel":"felt","fight":"fought","find":"found",
    "fly":"flew","forget":"forgot","forgive":"forgave","freeze":"froze","get":"got",
    "give":"gave","go":"went","grow":"grew","have":"had","hear":"heard",
    "hide":"hid","hold":"held","keep":"kept","know":"knew","lead":"led",
    "leave":"left","lend":"lent","lose":"lost","make":"made","mean":"meant",
    "meet":"met","pay":"paid","read":"read","ride":"rode","ring":"rang",
    "rise":"rose","run":"ran","say":"said","see":"saw","sell":"sold",
    "send":"sent","sing":"sang","sit":"sat","sleep":"slept","speak":"spoke",
    "spend":"spent","stand":"stood","steal":"stole","swim":"swam","take":"took",
    "teach":"taught","tell":"told","think":"thought","throw":"threw","understand":"understood",
    "wake":"woke","wear":"wore","win":"won","write":"wrote",
}
WRONG_IRREGULAR = {base + "ed": past for base, past in IRREGULAR.items()
                   if past not in {base + "ed", base} and "/" not in past}
WRONG_IRREGULAR.update({"buyed":"bought","eated":"ate","taked":"took","seed":"saw",
                        "goed":"went","writed":"wrote","runned":"ran","thinked":"thought",
                        "catched":"caught","teached":"taught","bringed":"brought"})
PAST_TO_BASE = {past: base for base, past in IRREGULAR.items() if "/" not in past}

BRITISH = {"color":"colour","favorite":"favourite","center":"centre","theater":"theatre",
           "neighbor":"neighbour","honor":"honour","organize":"organise","organized":"organised",
           "traveling":"travelling","traveled":"travelled","canceled":"cancelled",
           "realize":"realise","apologize":"apologise","meter":"metre","catalog":"catalogue"}
TYPOS = {"becouse":"because","definately":"definitely","seperate":"separate","recieve":"receive",
         "freind":"friend","beutiful":"beautiful","resturant":"restaurant","wich":"which",
         "thier":"their","alot":"a lot","untill":"until","happend":"happened",
         "suprise":"surprise","exited":"excited","memmorable":"memorable","tommorow":"tomorrow",
         "begining":"beginning","writting":"writing","enjoyd":"enjoyed","visitted":"visited"}
OVERUSED = {"very":"Use a stronger adjective.","nice":"Try pleasant, enjoyable or kind.",
            "good":"Try excellent, enjoyable, useful or memorable.","bad":"Try unpleasant, terrible or disappointing.",
            "thing":"Use a precise noun.","things":"Use precise nouns.","a lot":"Try many, much or frequently."}
CONNECTORS = ["because","however","although","after that","finally","first","next","then",
              "while","when","before","after","therefore","as a result","for example","in the end"]
VERBS = set(IRREGULAR) | set(IRREGULAR.values()) | {"am","is","are","was","were","been","being",
    "did","does","play","played","visit","visited","enjoy","enjoyed","feel","felt","seem","seemed",
    "like","liked","love","loved","want","wanted","walk","walked","talk","talked","arrive","arrived",
    "decide","decided","celebrate","celebrated","remember","remembered","help","helped","stay","stayed"}


@dataclass
class Issue:
    category: str
    original: str
    start: int
    end: int
    correction: str
    explanation: str
    rule_id: str
    section: str = "writing"


def _issue(items: list[Issue], category: str, match: re.Match | None, original: str,
           start: int, correction: str, explanation: str, rule_id: str, section: str) -> None:
    end = start + len(original)
    if any(start < old.end and old.start < end and old.rule_id == rule_id for old in items):
        return
    items.append(Issue(category, original, start, end, correction, explanation, rule_id, section))


def analyse(text: str, section: str = "writing", target_min: int = 120,
            target_max: int = 180) -> dict:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    words = list(WORD_RE.finditer(text))
    lower_words = [m.group().lower().replace("’", "'") for m in words]
    issues: list[Issue] = []

    for m in words:
        word = m.group().lower()
        if word in WRONG_IRREGULAR:
            _issue(issues,"Irregular verbs",m,m.group(),m.start(),WRONG_IRREGULAR[word],
                   f'“{m.group()}” is not the standard past form. Use “{WRONG_IRREGULAR[word]}”.',"irregular-past",section)
        elif word in BRITISH:
            _issue(issues,"British spelling",m,m.group(),m.start(),BRITISH[word],
                   "Use the British English spelling.","british-spelling",section)
        elif word in TYPOS:
            _issue(issues,"Spelling",m,m.group(),m.start(),TYPOS[word],
                   f'The standard spelling is “{TYPOS[word]}”.',"common-typo",section)

    for m in re.finditer(r"\b(did|didn't|did not)\s+([A-Za-z]+)\b", text, re.I):
        form = m.group(2).lower()
        base = PAST_TO_BASE.get(form)
        if base or form.endswith("ed"):
            suggestion = base or re.sub(r"ed$", "", form)
            _issue(issues,"Verb form after did",m,m.group(2),m.start(2),suggestion,
                   "After did or didn't, use the base form of the verb.","did-base",section)

    past_context = bool(re.search(r"\b(yesterday|last\s+(?:week|weekend|night|month|year|summer)|ago|in\s+20\d{2})\b",text,re.I))
    if past_context:
        bases = "|".join(sorted((re.escape(x) for x in IRREGULAR), key=len, reverse=True))
        for m in re.finditer(rf"\b(I|we|he|she|they)\s+({bases})\b", text, re.I):
            base = m.group(2).lower()
            correction = IRREGULAR.get(base, "")
            if correction and "/" not in correction:
                _issue(issues,"Tense",m,m.group(2),m.start(2),correction,
                       "The time expression places this event in the past, so use the past form.","past-context",section)

    agreement = [
        (r"\b(I)\s+(is|are|has|does|goes)\b",{"is":"am","are":"am","has":"have","does":"do","goes":"go"}),
        (r"\b(he|she|it)\s+(are|were|have|go|do|don't)\b",{"are":"is","were":"was","have":"has","go":"goes","do":"does","don't":"doesn't"}),
        (r"\b(we|they|you)\s+(is|was|has|goes|doesn't)\b",{"is":"are","was":"were","has":"have","goes":"go","doesn't":"don't"}),
    ]
    for pattern, forms in agreement:
        for m in re.finditer(pattern,text,re.I):
            replacement=forms[m.group(2).lower()]
            _issue(issues,"Subject-verb agreement",m,m.group(2),m.start(2),replacement,
                   f'Use “{replacement}” with the subject “{m.group(1)}”.',"subject-verb",section)

    for m in re.finditer(r"\b(a)\s+([aeiou][A-Za-z]*)",text,re.I):
        if not re.match(r"(?:uni|use|euro|one)",m.group(2),re.I):
            _issue(issues,"Articles",m,m.group(1),m.start(1),"an","Use “an” before a vowel sound.","a-an",section)
    for m in re.finditer(r"\b(an)\s+([bcdfgjklmnpqrstvwxyz][A-Za-z]*)",text,re.I):
        if not re.match(r"(?:hour|honest|honour|heir)",m.group(2),re.I):
            _issue(issues,"Articles",m,m.group(1),m.start(1),"a","Use “a” before a consonant sound.","an-a",section)
    places="park|market|cinema|beach|zoo|library|restaurant|museum|airport|station"
    for m in re.finditer(rf"\b(to|at)\s+({places})\b",text,re.I):
        _issue(issues,"Articles",m,m.group(2),m.start(2),"the "+m.group(2),
               "Use “the” when referring to this specific place.","place-article",section)

    for m in re.finditer(r"\bi\b",text):
        _issue(issues,"Capitalisation",m,"i",m.start(),"I","The pronoun “I” is always capitalised.","capital-i",section)
    for m in re.finditer(r"(^|[.!?]\s+)([a-z])",text):
        start=m.start(2)
        _issue(issues,"Capitalisation",m,m.group(2),start,m.group(2).upper(),
               "Start every sentence with a capital letter.","sentence-capital",section)
    for m in re.finditer(r" {2,}",text):
        _issue(issues,"Spacing",m,m.group(),m.start()," ","Use one space between words.","double-space",section)
    for m in re.finditer(r"\b([A-Za-z']+)\s+\1\b",text,re.I):
        _issue(issues,"Repeated word",m,m.group(),m.start(),m.group(1),
               "This word appears twice accidentally.","repeated-word",section)
    for m in re.finditer(r"([A-Za-z])([,;:!?])(?=[A-Za-z])|([a-z])(\.)(?=[A-Z])",text):
        _issue(issues,"Punctuation",m,m.group(),m.start(),m.group()+" ",
               "Put a space after punctuation.","punctuation-space",section)
    for m in re.finditer(r"(^|[.!?]\s+)(Finally|However|First|Next|After that|In the morning|In the evening)\s+",text,re.I):
        _issue(issues,"Punctuation",m,m.group(2),m.start(2),m.group(2)+",",
               "Add a comma after an opening linking phrase.","opening-comma",section)
    for m in re.finditer(r"\b[^.!?\n]{2,},\s+(I|he|she|we|they|it)\s+(?:was|were|went|had|did|came|saw|[a-z]+ed)\b",text,re.I):
        comma=text.find(",",m.start(),m.end())
        _issue(issues,"Comma splice",m,",",comma,". ",
               "A comma alone cannot join two complete sentences. Use a full stop or a connector.","comma-splice",section)

    sentence_matches=list(re.finditer(r"[^.!?\n]+(?:[.!?]+|$)",text))
    for sentence in sentence_matches:
        sentence_words=WORD_RE.findall(sentence.group())
        if len(sentence_words)>35:
            _issue(issues,"Run-on sentence",sentence,sentence.group().strip()[:45]+"…",sentence.start(),"",
                   f"This sentence has {len(sentence_words)} words. Split it into shorter sentences.","run-on",section)
        low={w.lower() for w in sentence_words}
        has_verb=bool(low & VERBS) or any(w.endswith(("ed","ing")) for w in low)
        if len(sentence_words)>=4 and not has_verb:
            _issue(issues,"Missing verb",sentence,sentence.group().strip(),sentence.start(),"",
                   "This may be an incomplete sentence because no clear verb was found.","missing-verb",section)
    if text.strip() and not re.search(r"[.!?][\"'’”)]*$",text.strip()):
        pos=len(text.rstrip())
        _issue(issues,"Punctuation",None,"end of answer",pos,".",
               "Finish the final sentence with punctuation.","end-punctuation",section)

    for phrase, explanation in OVERUSED.items():
        for m in re.finditer(r"\b"+re.escape(phrase)+r"\b",text,re.I):
            _issue(issues,"Vocabulary",m,m.group(),m.start(),"",explanation,"overused-word",section)

    issues.sort(key=lambda x:(x.start,x.end,x.rule_id))
    # Exact duplicates can arise where rules share a broad pattern.
    unique=[]; seen=set()
    for item in issues:
        key=(item.start,item.end,item.category,item.correction)
        if key not in seen: seen.add(key); unique.append(item)
    issues=unique
    word_count=len(words)
    sentences=max(1,len([s for s in sentence_matches if WORD_RE.search(s.group())]))
    unique_ratio=(len(set(lower_words))/word_count) if word_count else 0
    connector_count=sum(len(re.findall(r"\b"+re.escape(c)+r"\b",text,re.I)) for c in CONNECTORS)
    categories=Counter(i.category for i in issues)
    grammar_cats={"Irregular verbs","Tense","Verb form after did","Subject-verb agreement","Articles","Missing verb","Comma splice","Run-on sentence"}
    mechanics_cats={"Spelling","British spelling","Punctuation","Capitalisation","Spacing","Repeated word"}
    rate=lambda cats: (sum(categories[c] for c in cats)*100/word_count) if word_count else 100
    grammar_rate=rate(grammar_cats); mechanics_rate=rate(mechanics_cats)
    score_rate=lambda value: 5 if value<=2 else 4 if value<=4 else 3 if value<=7 else 2 if value<=11 else 1
    vocabulary=1
    if unique_ratio>=.45:vocabulary=2
    if unique_ratio>=.55:vocabulary=3
    if unique_ratio>=.65:vocabulary=4
    if unique_ratio>=.72:vocabulary=5
    if connector_count>=4:vocabulary=min(5,vocabulary+1)
    if categories["Vocabulary"]*100/max(1,word_count)>3:vocabulary=max(1,vocabulary-1)
    details={"who":bool(re.search(r"\b(I|we|my)\b",text,re.I)),
             "where":bool(re.search(r"\b(at|in|to)\s+(?:the|a|my)\b",text,re.I)),
             "when":bool(re.search(r"\b(yesterday|last|morning|evening|day|year|ago|20\d{2})\b",text,re.I)),
             "why":bool(re.search(r"\b(because|so|important|proud|happy)\b",text,re.I)),
             "past":bool(re.search(r"\b(was|were|went|had|did|felt|[A-Za-z]+ed)\b",text,re.I))}
    detail_count=sum(details.values())
    length_band=2 if target_min<=word_count<=target_max else 1 if target_min-20<=word_count<=target_max+40 else 0
    task=5 if length_band==2 and detail_count>=4 else 4 if length_band>=1 and detail_count>=3 else 3 if word_count>=70 and detail_count>=3 else 2 if word_count>=40 and detail_count>=1 else 1
    scores={"grammar":score_rate(grammar_rate),"spelling_punctuation":score_rate(mechanics_rate),
            "vocabulary":vocabulary,"task_length":task}
    total=sum(scores.values())
    topic_flag="Likely on topic" if detail_count>=4 and word_count>=60 else "Teacher review required"
    calculated_level="B2" if total>=18 else "B1" if total>=14 else "A2" if total>=10 else "Below A2"
    # A polished pasted article can have perfect grammar while completely missing
    # the task. Do not present that as a confident placement.
    level=calculated_level if topic_flag=="Likely on topic" else "Teacher review required"
    task_feedback=[]
    if word_count<target_min: task_feedback.append(f"Write at least {target_min} words; this answer has {word_count}.")
    if word_count>target_max: task_feedback.append(f"The target is {target_min}–{target_max} words; this answer has {word_count}.")
    labels={"who":"say who was involved","where":"describe where it happened","when":"make the time clear","why":"explain why it mattered","past":"use past-tense narration"}
    task_feedback.extend(f"Add details to {message}." for key,message in labels.items() if not details[key])
    if not task_feedback: task_feedback.append("The answer includes the main task details; a teacher should still confirm relevance and coherence.")
    lesson_items=[]
    for category,count in categories.most_common():
        if category in LESSON_BY_CATEGORY:
            lesson={**LESSON_BY_CATEGORY[category],"count":count}
            example=next(i for i in issues if i.category==category)
            lesson["student_example"]={"original":example.original,"correction":example.correction}
            lesson_items.append(lesson)
        if len(lesson_items)==3:break
    return {"checker_version":CHECKER_VERSION,"formula_version":FORMULA_VERSION,
            "metrics":{"word_count":word_count,"sentence_count":sentences,
                       "average_sentence_length":round(word_count/sentences,1),
                       "unique_word_ratio":round(unique_ratio,3),"connector_count":connector_count},
            "issues":[asdict(i) for i in issues],"category_counts":dict(categories),
            "scores":scores,"total":total,"level":level,
            "errors_per_100_words":round(len(issues)*100/max(1,word_count),1),
            "topic_flag":topic_flag,"task_details":details,"task_feedback":task_feedback,
            "calculated_level":calculated_level,"lessons":lesson_items,
            "formula":"Grammar and mechanics use errors per 100 words: ≤2=5, ≤4=4, ≤7=3, ≤11=2, >11=1. Vocabulary uses unique-word ratio, connectors and overused words. Task score uses the 120–180 word target. Total: A2=10, B1=14, B2=18.",
            "notice":"Automated first-pass check—teacher to confirm. It may miss errors or flag correct sentences. Relevance, coherence and natural style are not judged automatically. Speaking audio is assessed by a teacher."}


def analyse_submission(writing: str, transcripts: Iterable[str]) -> dict:
    writing_report=analyse(writing,"writing")
    speaking=[]
    for number,text in enumerate(transcripts,1):
        speaking.append(analyse(text,f"speaking_{number}",0,300) if text.strip() else None)
    return {"writing":writing_report,"speaking":speaking}
