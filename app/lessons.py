"""Fixed, non-generative learning material used by the deterministic checker."""

LESSONS = [
    {"id":"past-simple","category":"Tense","title":"Keep stories in the past","rule":"Use past forms when describing finished events.","examples":"Yesterday I went home. | We played football.","mistake":"Yesterday I go home."},
    {"id":"irregular-verbs","category":"Irregular verbs","title":"Learn irregular past forms","rule":"Some common verbs change form instead of taking -ed.","examples":"go → went | buy → bought | eat → ate","mistake":"I buyed a present."},
    {"id":"did-base","category":"Verb form after did","title":"Use the base verb after did","rule":"Did and didn't already show the past, so the next verb stays in its base form.","examples":"Did you go? | I didn't see it.","mistake":"I didn't went."},
    {"id":"subject-verb","category":"Subject-verb agreement","title":"Match subjects and verbs","rule":"He, she and it normally take a singular verb; I, we, you and they use the matching form.","examples":"She likes tea. | They were ready.","mistake":"She like tea."},
    {"id":"articles","category":"Articles","title":"Use a, an and the","rule":"Use a/an for one non-specific countable thing and the for something specific.","examples":"an idea | a friend | the park near my house","mistake":"I went to park."},
    {"id":"capital-i","category":"Capitalisation","title":"Always capitalise I","rule":"The pronoun I is always written with a capital letter.","examples":"My friend and I arrived. | I was happy.","mistake":"Then i went home."},
    {"id":"sentence-capital","category":"Capitalisation","title":"Start with a capital letter","rule":"Begin every sentence with a capital letter.","examples":"It was sunny. We went outside.","mistake":"it was sunny."},
    {"id":"end-punctuation","category":"Punctuation","title":"Finish each sentence","rule":"End a statement with a full stop and a direct question with a question mark.","examples":"We arrived early. | Where did you go?","mistake":"We arrived early"},
    {"id":"punctuation-space","category":"Punctuation","title":"Space after punctuation","rule":"Put one space after a comma, full stop, colon or semicolon.","examples":"First, we ate. Then, we left.","mistake":"First,we ate."},
    {"id":"opening-comma","category":"Punctuation","title":"Commas after opening phrases","rule":"Use a comma after an opening time word or linking phrase.","examples":"Finally, we went home. | After that, we ate.","mistake":"Finally we went home."},
    {"id":"comma-splice","category":"Comma splice","title":"Join sentences correctly","rule":"Do not join two complete sentences using only a comma.","examples":"I was tired, so I slept. | I was tired. I slept.","mistake":"I was tired, I slept."},
    {"id":"run-on","category":"Run-on sentence","title":"Control sentence length","rule":"Split very long sentences so each one expresses a clear main idea.","examples":"We arrived late. Everyone was waiting.","mistake":"We arrived and everyone was waiting and then we..."},
    {"id":"sentence-verb","category":"Missing verb","title":"Give every sentence a verb","rule":"A complete sentence normally needs a subject and a verb.","examples":"My best friend was there. | The journey felt exciting.","mistake":"My best friend at the party."},
    {"id":"double-space","category":"Spacing","title":"Use single spaces","rule":"Use one space between words.","examples":"We went to the beach.","mistake":"We  went to the beach."},
    {"id":"repeated-word","category":"Repeated word","title":"Remove accidental repetitions","rule":"Read slowly to catch a word typed twice.","examples":"We went to the market.","mistake":"We went to to the market."},
    {"id":"british-spelling","category":"British spelling","title":"Use British spelling consistently","rule":"Use British forms such as colour, centre and travelled.","examples":"favourite colour | city centre | travelled","mistake":"favorite color"},
    {"id":"common-spelling","category":"Spelling","title":"Check common spellings","rule":"Review frequently confused letter patterns and silent letters.","examples":"because | definitely | beautiful","mistake":"becouse | definately"},
    {"id":"precise-vocabulary","category":"Vocabulary","title":"Choose precise words","rule":"Replace general words with exact nouns, verbs and adjectives.","examples":"a delicious meal | an unforgettable journey","mistake":"a very good thing"},
    {"id":"connectors","category":"Connectors","title":"Connect your ideas","rule":"Use linking words to show time, reason and contrast.","examples":"because | however | after that | finally","mistake":"I woke up. I ate. I left."},
    {"id":"present-third","category":"Subject-verb agreement","title":"He, she, it plus -s","rule":"In the present simple, most verbs take -s after he, she or it.","examples":"He works. | She enjoys reading.","mistake":"He work every day."},
    {"id":"was-were","category":"Subject-verb agreement","title":"Choose was or were","rule":"Use was with I/he/she/it and were with we/you/they.","examples":"I was proud. | They were excited.","mistake":"They was excited."},
    {"id":"countable-nouns","category":"Articles","title":"Check singular countable nouns","rule":"A singular countable noun normally needs a/an, the or another determiner.","examples":"a gift | my friend | the building","mistake":"I bought gift."},
    {"id":"past-time","category":"Tense","title":"Notice past-time markers","rule":"Words such as yesterday, last and ago normally require past-tense verbs.","examples":"Last weekend, I visited Lahore.","mistake":"Last weekend, I visit Lahore."},
    {"id":"paragraph-flow","category":"Style","title":"Build a clear sequence","rule":"Organise the event from beginning to end using time connectors.","examples":"First... After that... Finally...","mistake":"Ideas appear in an unclear order."},
    {"id":"proofread","category":"Typing","title":"Proofread once slowly","rule":"Read the finished answer once for missing words, repeated words and punctuation.","examples":"Read sentence by sentence before submitting.","mistake":"Submitting immediately without a final check."},
]

LESSON_BY_CATEGORY = {}
for lesson in LESSONS:
    LESSON_BY_CATEGORY.setdefault(lesson["category"], lesson)

