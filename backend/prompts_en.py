import random


BASE_SYSTEM_PROMPT = """You are a narrator describing the player's career story at Hooli.

Hooli is a fictional Silicon Valley tech company full of absurd corporate culture: too many processes, blurry ownership, frequent reorganizations, and language that is always polished until it stops meaning anything.

[Narration Rules]
- Use second person "you"
- Do not make decisions for the player
- Put NPC dialogue in quotes
- Avoid ornamental quote marks
- Move the scene forward with concrete developments; do not end with vague summaries
- Keep the tone steady, cool-headed, mildly satirical, and dryly funny in a workplace way
- Your narration must be 100-160 words total in English. If you exceed 160 words, your response is invalid.
- For technical issues, only describe who owns the problem, where it is stuck, and what the risk is; do not expand into implementation detail
- Bad example: "The Connection Timeout aligns with the batch processing window, so this looks like a race condition."
- Good example: "The logs are full of errors, the timing lines up with the neighboring team's deploy, and nobody is willing to admit it might be theirs."
- Focus on workplace decisions and interpersonal dynamics (risk communication, priority alignment, cross-team collaboration)
- Use natural English workplace vocabulary
- Keep English concise and avoid unnecessary jargon
- Describe scenes briefly; avoid long descriptive passages
- Keep any single character speaking turn to at most two sentences inside quotes
- You may include one short piece of background noise, such as a company-wide email, a random Slack message from a coworker (small talk, gossip, complaints, sarcasm, nagging, or questions), an elevator notice, or an event announcement

[Target Rhythm - keep this cadence in every turn; do not switch into formal prose just because later instructions are structured]
- Not funny (do not do this): You send a meeting invite and everyone declines or ignores it.
- Funny (do this): The PM shows up, but spends the entire time happily sharing a completely unrelated OKR details. The Tech Lead arrives and opens with a bomb, "We evaluated this architecture a year ago. Integration will be a big challenge. It's a good opportunity to demonstrate your skills."

[Example 1]
Monday morning. Can barely get up. The company's "strongly recommended" AI digest pops up with today's summary: "All Hands meeting! Submit your questions now! Gavin will answer them personally." It's been summarizing the same message for a week straight. Hard to tell if this is Gavin deliberately burying the feed, or the AI digest working as designed.

This sprint's project: classic team flavor. PM can't explain what they want, clients are furious, dev time is two weeks. Zero technical depth — just mindless CRUD, the kind where if you brought it to the tech lead to look engaged, they wouldn't even bother responding. Another project not worth putting on your performance review. Where's the promotion scope? You look up, as if the ceiling might have answers. A ceiling AC unit drips on your face.

You wipe away what could be tears, sweat, or HVAC water, and decide...

The point of this example: short sentences, concrete details over adjectives, satire that comes from the situation itself instead of explaining that the situation is absurd, and no buzzword soup.

[Example 2]
You finish the company's free lunch. Today's "balanced healthy meal" is yesterday's "balanced healthy meal" in a slightly different container. Free food is free food. This is the closest thing to a belief system you have left. 
                                                                                                                   
In the afternoon carb fog, you unlock your phone, lock it, unlock it again, and check your inbox for what might be the hundredth time. A new subject line: "Jessica 1:1." Jessica is a VP in your org. VPs don't book 1:1s with ICs to chat about the weather. This is either your big break or the beginning of a very specific kind of problem.
                                                                                                                    
Kevin from the next desk materializes at your shoulder — you never hear him approach, only arrive. "Did you see? Larry from the other team got a leadership 1:1. I think our org is about to take off." He pulls up three Slack channels as evidence. One is #random. His analysis connects org restructuring rumors, a cafeteria menu change, and a VP's LinkedIn post into a theory so internally consistent you almost forget none of it is real.

Thinking about Jessica's 1:1, you decide...

[Example 3: second-turn response]
In the ticket history — which reads less like documentation and more like a ball of yarn someone fought and lost to — you find one useful clue: last month, Eddie from the neighboring team, who has since quit, mentioned a mysterious ancient service called Eggdrop.
After some digging, you realize Eggdrop is deeply entangled with your service. You turn to the company's internal search tool, which has never once returned a relevant result, and somehow, against all precedent, locate the owner of Eggdrop.
You send a carefully organized list of questions, hoping to rescue your team's service before it collapses further. The owner responds within minutes: "Our top priority is solving user problems."                          
                                                                                          
On meeting day, the company's famously stable video software spends the first ten minutes dying in fragments — frozen faces, phantom echoes, a screen share of someone's desktop wallpaper. When the call finally stabilizes, every question gets the same answer: "That is a great question. Let me confirm with the team and get back to you." Same phrasing, same cadence, five times in a row, like an NPC with one dialogue tree.                  
It slowly dawns on you: the owner was onboarded last week. "Our top priority is solving user problems" isn't a commitment. It's a default line.
You begin to suspect the ten minutes of video software failure may also be standard operating procedure.

At that point Shiva — the quiet coworker who barely speaks, who silently eats through every team lunch like a monk observing a vow — drifts past your desk and drops a single sentence: "Eggdrop protein API. That's the answer you want." No context. No follow-up. Already walking away.                                                            
You look it up and immediately hit a treasure chest of clues. Your next move is...

[Example 4: second-turn response]
You contact PM Jimmy right away to clarify the project's priority and scope.
                                                                                                                    
A PM arriving five minutes late is so normal it barely registers as lateness. You wait. At this point, if a PM showed up on time, you'd quietly suspect something was wrong with their career.                                   
   
The moment Jimmy sits down, he starts a sequence:                                                                 
"Let me get some water first. I have been talking nonstop for an hour."
"The boss cares a lot about this project. Do not worry about impact or visibility. This is absolutely promotion material."                                                                                                        
"The customer is a little tricky, though." (followed by what feels like a thousand words describing the customer)
"The key is that milestone 1 MVP has to look good. The demo needs to impress."                                    
"Everything else can be pushed to later milestones and described as future work. You know what I mean, right?"    
   
For reasons unknown, one sip of water fully restores Jimmy's HP and powers another uninterrupted thirty-minute monologue, plus a three-minute overtime encore.
                                                                                                                    
"I need to run to my next meeting. Good luck to us. Hooli Hooli!"

You spoke three sentences in thirty minutes. Two were "mm-hmm." You console yourself with the possibility that somewhere inside that wall of sound, there was one useful signal.

What do you do next?
"""

NAME_POOL = [
    "Amber",
    "Alex",
    "Brian",
    "Brittany",
    "Casey",
    "Chris",
    "Connor",
    "David",
    "Jamie",
    "Jennifer",
    "Jordan",
    "Kevin",
    "Kim",
    "Mark",
    "Michelle",
    "Morgan",
    "Priya",
    "Rachel",
    "Rahul",
    "Ryan",
    "Sam",
    "Sarah",
    "Taylor",
    "Tyler",
    "Vinh",
    "Wei",
    "Yin",
    "Yvonne"
]


MANAGERS = [
    {
        "id": "nice_but_useless",
        "display_desc": "Nice but useless",
        "ai_personality_desc": "Replies fairly quickly and often gets back to you fast; the content is warm, polite, and emotionally soothing, but almost never actionable. Message style: one warm paragraph full of emotional support that leaves you with no concrete next step.",
    },
    {
        "id": "competent_but_busy",
        "display_desc": "Excellent but busy",
        "ai_personality_desc": "Replies slowly and often takes a long time to answer; the content usually shows judgment and points in the right direction, but it is very short and often only leaves one key sentence. Message style: one or two lines, direct guidance, no explanation, no comfort.",
    },
]

BUDDIES = [
    {
        "id": "helpful_but_talks_too_much",
        "display_desc": "Helpful and chatty",
        "ai_personality_desc": "Replies quickly and usually gets back to you fast; the content is long and fragmented, throwing out lots of background information and suggestions. Sometimes it helps, sometimes it misleads. Message style: one big block of text containing hearsay, guesses, and uncertain information that leaves you more confused than before.",
    },
    {
        "id": "disappeared",
        "display_desc": "Mascot",
        "ai_personality_desc": "Replies extremely slowly and often reads without answering or shows up much later; the content is usually minimal, often just one vague sentence, and not actually useful. Message style: one sentence appears occasionally, then they vanish again.",
    },
]

TEAM_MEMBERS = [
    {
        "id": "strong_senior",
        "display_desc": "Sharp senior",
        "ai_personality_desc": "Replies quickly and usually gets back to you fast; the content is direct, sharp, and effective, pointing out the core problem and a viable direction. Their code reviews are ruthless, and they will ask about edge cases. Message style: one or two sentences, precise and cutting, no explanation, no comfort, no wasted words.",
    },
    {
        "id": "useless_colleague",
        "display_desc": "Useless coworker",
        "ai_personality_desc": "Reply speed is unstable. Sometimes it looks like they responded, but they often disappear right before the deadline. The content is not very useful; they usually say they are busy with higher-priority work or dump the responsibility back on you. Message style: one evasive sentence, then gone.",
    },
    {
        "id": "political_insider",
        "display_desc": "Political gossip broker",
        "ai_personality_desc": "Replies at a medium pace and usually answers, just not immediately; the content leans into political wording and side-channel hints, implying the direction of the wind without ever stating the answer plainly. Message style: one suggestive sentence, usually ending with something like 'you know how it is' or 'do not say I said that,' and never actually finishing the thought.",
    },
    {
        "id": "friendly_but_busy",
        "display_desc": "Friendly but busy",
        "ai_personality_desc": "Replies slowly and often sends one sentence after a delay; the tone is friendly but thin, usually offering brief support without much practical help. Message style: one warm sentence with no real substance.",
    },
    {
        "id": "anxious_but_helpful",
        "display_desc": "Anxious but useful",
        "ai_personality_desc": "Replies very quickly and often provides key clues, but is intensely anxious about every small signal. They frequently send messages worrying about being laid off, reorganized away, or abandoned by their boss. Message style: three or four short messages in a row, one or two sentences each, mixing useful information with anxious speculation.",
    },
]

PROJECTS = [
    {
        "id": "small_engineering_project",
        "title": "Small Engineering Project",
        "weight": 10,
        "rounds": 2,
        "unlock": {},
        "story": "You are assigned an ops ticket with unclear requirements. All you know is that something is wrong, the customer is upset, and nobody can say where the problem actually is. It has to be delivered before next week's customer meeting so nobody gets nailed to the wall. This project is a tiny speck inside operation excellence, with impact and visibility somewhere near zero. There may be no glory in it, but there is definitely labor, which is why nobody wants it. You are that labor.",
        "perf_review": {
            "achievements": [
                {
                    "label": "Clarified the customer issue",
                    "hook": "You turned a customer-facing ops ticket nobody wanted from a vague complaint into a concrete, workable problem",
                    "match_terms": ["customer", "ops", "ticket", "root cause", "clarify", "complaint", "issue", "unhappy", "investigation"],
                    "framings": {
                        "A": "Emphasize that you proactively clarified what was actually blocking the customer instead of handing the vague ops ticket back untouched.",
                        "B": "Emphasize that you turned low-visibility grunt work into an actionable path so the team at least had something credible before the customer meeting.",
                    },
                },
                {
                    "label": "Carried low-visibility work",
                    "hook": "You stabilized an unwanted low-visibility task and kept it from exploding before the customer meeting",
                    "match_terms": ["low visibility", "grunt work", "customer meeting", "delivery", "containment", "stabilize", "next week", "meeting"],
                    "framings": {
                        "A": "Emphasize that you contained risk inside work that earns no credit, preventing the customer meeting from turning into a public execution.",
                        "B": "Emphasize that you took on operation excellence work nobody wanted and kept the basic floor from springing another leak.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You turn a vague customer complaint into a concrete problem, proactively narrow the risk, and deliver a credible handling result before the customer meeting.",
            "neutral": "You get the ops ticket into a state that can be explained, but the work is passive and the root cause, risk, or follow-up is still not clearly articulated.",
            "bad": "You simply bounce the problem back to the requester, vaguely declare it fixed, or let the risk drag all the way into the customer meeting without clarifying the cause.",
        },
        "affects": {
            "good": {"tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "medium_engineering_project",
        "title": "Medium Engineering Project",
        "weight": 10,
        "rounds": 2,
        "unlock": {},
        "story": "A PM specifically asks you to own a mid-sized project. It has some impact and visibility, but not much: not so small that it disappears from a performance review, not so large that it becomes compelling promotion evidence. The customer is difficult. After A comes B, after B comes C. What should be a medium project has started to show clear signs of mutating into a large one that never stops growing. Who knows whether staying on this thing means missing your shot at a real promotion-scope project this year?",
        "perf_review": {
            "achievements": [
                {
                    "label": "Stopped scope creep",
                    "hook": "You carved boundaries around a PM-assigned mid-sized project instead of letting customer add-ons turn it into a sinkhole",
                    "match_terms": ["PM", "scope", "customer", "boundary", "add-on", "range", "A", "B", "C", "growth"],
                    "framings": {
                        "A": "Emphasize that you proactively drew boundaries while the customer kept adding requests, preventing the mid-sized project from turning into a bottomless pit.",
                        "B": "Emphasize that you turned the PM's vague expectations into a deliverable scope so the project did not expand out of control.",
                    },
                },
                {
                    "label": "Made limited impact reviewable",
                    "hook": "Inside a project with limited impact and ever-growing demands, you preserved a concrete deliverable worth writing into review",
                    "match_terms": ["impact", "visibility", "delivery", "review", "customer", "medium", "project", "complete"],
                    "framings": {
                        "A": "Emphasize that you preserved a deliverable visible enough for review despite limited visibility instead of being dragged under by additional requests.",
                        "B": "Emphasize that you maintained a delivery rhythm between the customer and the PM so the project produced results without expanding forever.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You align priorities with the PM and customer, clearly define scope boundaries, and deliver steadily without letting the mid-sized project grow out of control.",
            "neutral": "You complete the main delivery, but you are passive about additional requests and do not fully align scope, tradeoffs, or follow-up risk.",
            "bad": "You let the customer's asks keep expanding without aligning tradeoffs with the PM, or scope creep drags delivery into quality and schedule chaos.",
        },
        "affects": {
            "good": {"tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "medium_project_ops",
        "title": "Medium Project / Ops",
        "weight": 8,
        "rounds": 2,
        "unlock": {"tech_min": 4},
        "story": "You spot a long-ignored issue yourself from oncall ops noise and manage to claim ownership of the backlog item. It is not a huge project, but it is messy and technically deep; if you solve it, the whole team will thank you. The reason it has been unresolved for so long is simple: it is profoundly annoying.",
        "perf_review": {
            "achievements": [
                {
                    "label": "Found the issue in oncall noise",
                    "hook": "You were not passively assigned work; you dug a worthwhile backlog problem out of oncall noise yourself",
                    "match_terms": ["oncall", "ops", "ticket", "backlog", "discover", "issue", "proactive", "ownership"],
                    "framings": {
                        "A": "Emphasize that you identified a genuinely valuable problem inside oncall noise instead of just processing tickets one by one.",
                        "B": "Emphasize that you turned a long-unowned backlog item into a formal project and closed a hole that had been draining the team repeatedly.",
                    },
                },
                {
                    "label": "Untangled tricky tech debt",
                    "hook": "You broke down a small but technically deep problem into something solvable so the team did not have to keep being dragged by it",
                    "match_terms": ["technical", "complex", "messy", "tech debt", "break down", "team", "solve", "deep"],
                    "framings": {
                        "A": "Emphasize that you decomposed a small but deep piece of technical debt so the team no longer had to keep getting interrupted by the same oncall pain.",
                        "B": "Emphasize that you took on high-friction work and pushed it steadily so the problem moved from 'everyone knows about it' to 'someone is actually closing it out.'",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You proactively identify a real issue from oncall or ops signals, claim ownership, and turn a complex backlog item into a plan that can move and close.",
            "neutral": "You take on the backlog item and move part of it forward, but the technical breakdown, risk sync, or closure plan remains fuzzy.",
            "bad": "You declare you will handle the backlog but never break out a real path, or you underestimate the complexity and leave the team stuck with it.",
        },
        "affects": {
            "good": {"tech": 1, "affinity": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "big_project_scope",
        "title": "Big Project / Scope",
        "weight": 4,
        "rounds": 3,
        "unlock": {"tech_min": 5, "visibility_min": 5},
        "story": "You finally get a project large enough to count as promotion scope. You are ready to make it count. Naturally, nothing is as straightforward as optimistic people pretend: a loud customer saying 'I need it tomorrow' and 'Why can't you give it to me next week?', a PM who knows almost nothing, upstream systems tangled in technical debt, and customer business logic held together by workaround vines. How do you cut through all of that and turn this into the achievement that puts shine on your promotion case?",
        "perf_review": {
            "achievements": [
                {
                    "label": "Held promotion scope together",
                    "hook": "You took ownership of a promotion-scale project and pulled the loud customer, vague PM, and upstream technical debt back into something that could move",
                    "match_terms": ["promotion", "scope", "customer", "PM", "upstream", "tech debt", "workaround", "large"],
                    "framings": {
                        "A": "Emphasize that you actively integrated the customer, PM, and upstream system constraints in a promotion-scope project so it could genuinely move forward.",
                        "B": "Emphasize that you absorbed noisy stakeholders and complicated technical debt without letting the project collapse into uncontrolled firefighting.",
                    },
                },
                {
                    "label": "Turned chaos into a delivery path",
                    "hook": "You translated customer business workarounds and upstream technical debt into a delivery path people could execute and evaluate",
                    "match_terms": ["path", "delivery", "business", "logic", "workaround", "tradeoff", "dependency", "milestone"],
                    "framings": {
                        "A": "Emphasize that you organized tangled business logic and technical dependencies into a delivery path that could actually be evaluated.",
                        "B": "Emphasize that you defined staged milestones under high expectations so the promotion-scope project became more than a vague grand plan.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You handle the high-pressure customer, vague PM, and upstream technical debt, clearly defining scope, tradeoffs, and milestones so the promotion-scale project moves steadily.",
            "neutral": "You move the large project forward, but stakeholder alignment, dependency risk, or the delivery path is still not clear enough.",
            "bad": "You let the customer pressure and PM ambiguity pull you around, fail to manage upstream technical debt and business workarounds, and the large project spins out.",
        },
        "affects": {
            "good": {"tech": 2, "visibility": 1},
            "bad": {"visibility": -1, "pip_potential": 1},
        },
    },
    {
        "id": "big_project_innovation",
        "title": "Big Project / Innovation",
        "weight": 3,
        "rounds": 3,
        "unlock": {"tech_min": 6, "visibility_min": 5},
        "story": "The big project you have wanted for ages finally arrives, which is exactly why it feels suspicious. Leadership loves it. It glows. The success or failure of the whole thing seems packed into the word innovation in the project title. Leadership wants a fancy story, your manager and tech lead insist on the newest technology, the highest standards, the most perfect design, all in the name of proving how much value engineers can create. You can feel the weight of this very visible crown.",
        "perf_review": {
            "achievements": [
                {
                    "label": "Made the innovation story real",
                    "hook": "You pulled leadership's fancy story back into engineering reality so the innovation project became more than a pretty slogan",
                    "match_terms": ["innovation", "fancy", "story", "leadership", "showcase", "land", "engineering", "value"],
                    "framings": {
                        "A": "Emphasize that you turned leadership's innovation narrative into an engineering plan that could actually land instead of leaving it as polished terminology.",
                        "B": "Emphasize that you balanced narrative and deliverability in a highly visible project so the fancy story had something real underneath it.",
                    },
                },
                {
                    "label": "Controlled new-tech impulse",
                    "hook": "While your manager and tech lead chased the highest possible standards, you kept hold of tradeoffs and risk instead of turning new technology into self-congratulation",
                    "match_terms": ["new technology", "highest standard", "perfect", "design", "tradeoff", "risk", "tech lead", "manager"],
                    "framings": {
                        "A": "Emphasize that you kept tradeoffs, risk, and landing cost visible under pressure to use the newest technology and highest standards.",
                        "B": "Emphasize that you did not blindly chase perfect design, but instead made the showcase project actually prove engineering value.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You align leadership's innovation narrative, your manager's expectations, and technical tradeoffs into one coherent line, producing a plan that has sparkle but can still land.",
            "neutral": "You take on the innovation project successfully, but the proposal is either too conservative or too theatrical, and the technical risk or feasibility is not fully explained.",
            "bad": "You get dragged around by the fancy story or the newest technology, ignore real tradeoffs, risk, and the delivery path, and the showcase project turns into an air castle.",
        },
        "affects": {
            "good": {"tech": 1, "visibility": 2},
            "bad": {"tech": -1, "visibility": -1, "pip_potential": 1},
        },
    },
    {
        "id": "bug_fix_sprint",
        "title": "Bug Fix Sprint",
        "weight": 8,
        "rounds": 2,
        "unlock": {},
        "story": "You are dropped into a bug-fix sprint and have to handle multiple production issues in a row.",
        "perf_review": {
            "achievements": [
                {
                    "label": "Stopped the bleeding",
                    "hook": "You first compressed the chaos into a manageable problem and prevented the blast radius from widening",
                    "match_terms": ["containment", "impact", "scope", "incident", "stabilize", "high pressure", "controlled"],
                    "framings": {
                        "A": "Emphasize that you narrowed the impact area inside chaos instead of letting the incident keep spreading outward.",
                        "B": "Emphasize that you stabilized the situation under pressure so the team could get back to a controllable state first.",
                    },
                },
                {
                    "label": "Tracked the real root cause",
                    "hook": "You did not stop at surface-level containment; you chased the issue all the way back to its real source",
                    "match_terms": ["root cause", "source", "investigation", "context", "clue", "real", "auth", "allowlist", "evidence", "log", "schedule", "batch"],
                    "framings": {
                        "A": "Emphasize that you investigated the root cause and rebuilt the context instead of only suppressing symptoms for a while.",
                        "B": "Emphasize that you proactively found the right people and assembled scattered clues into an actionable repair direction.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You stabilize the situation, communicate clearly, and reduce the chance of the same problem happening again.",
            "neutral": "You mostly complete the fix, but the approach is passive.",
            "bad": "The fix quality is unstable or the communication loses focus, causing repeated incidents or a wider blast radius.",
        },
        "affects": {
            "good": {"tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "system_design_rfc",
        "title": "System Design / RFC",
        "weight": 6,
        "rounds": 2,
        "unlock": {"tech_min": 3},
        "story": "You need to propose a cross-service RFC and answer challenges in review.",
        "perf_review": {
            "achievements": [
                {
                    "label": "Defined architectural tradeoffs",
                    "hook": "You turned vague requirements into a proposal with real tradeoffs instead of handing over a pretty document",
                    "match_terms": ["tradeoff", "proposal", "architecture", "requirements", "constraints", "rfc", "organize", "define"],
                    "framings": {
                        "A": "Emphasize that you proactively defined the important tradeoffs and constraints so the discussion had something concrete to evaluate.",
                        "B": "Emphasize that you organized a complicated problem into a proposal that could formally go to review and move the work forward.",
                    },
                },
                {
                    "label": "Absorbed review pressure",
                    "hook": "You answered challenges, filled in context, and kept the discussion from spinning out under review pressure",
                    "match_terms": ["review", "challenge", "feedback", "approval", "response", "pressure", "risk", "reviewer"],
                    "framings": {
                        "A": "Emphasize that you handled reviewer pushback and cross-team expectations so the discussion became more than people blocking each other.",
                        "B": "Emphasize that you surfaced risk and constraints early instead of letting the real problems explode at the end.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "The design tradeoffs are clear, you can respond to risk and feedback, and you move consensus forward.",
            "neutral": "The document is complete but the argument is ordinary and only meets the baseline.",
            "bad": "The important tradeoffs are unclear, or you become passively defensive in review and the work stalls.",
        },
        "affects": {
            "good": {"tech": 1, "visibility": 1},
            "bad": {"visibility": -1, "pip_potential": 1},
        },
    },
    {
        "id": "cross_team_collab",
        "title": "Cross-Team Collaboration",
        "weight": 6,
        "rounds": 2,
        "unlock": {"affinity_min": 2},
        "story": "You are assigned to work with an engineer from another team on a short-term project. Their team does not understand the goal the same way your team does, the work split was never clearly defined, but the deadline is extremely clear.",
        "perf_review": {
            "achievements": [
                {
                    "label": "Aligned cross-team goals",
                    "hook": "You pulled different teams' expectations back toward the same direction instead of letting the collaboration split into separate tracks",
                    "match_terms": ["cross-team", "align", "direction", "expectation", "collaboration", "split", "goal", "responsibility"],
                    "framings": {
                        "A": "Emphasize that you handled the goal gap across teams so the collaboration could at least move in one shared direction.",
                        "B": "Emphasize that you proactively clarified responsibility boundaries and work split so the entire burden did not end up on you.",
                    },
                },
                {
                    "label": "Kept the credit visible",
                    "hook": "You did not just get the work done; you made sure the contribution was seen instead of letting the other side walk away with all the credit",
                    "match_terms": ["credit", "contribution", "visible", "recognition", "stakeholder", "exposure", "visibility"],
                    "framings": {
                        "A": "Emphasize that you deliberately made stakeholders see your judgment and contribution instead of silently carrying the project.",
                        "B": "Emphasize that you held the relationship and the delivery together under collaborative chaos instead of letting the project spin out.",
                    },
                },
            ]
        },
        "rubric": {
            "good": "You align goals, split the work reasonably, and do not let the other side absorb all the credit.",
            "neutral": "The project gets finished, but the process is messy and your contribution is not clearly visible.",
            "bad": "The collaboration breaks down, the output quality is poor, or you carry most of the work while the credit goes elsewhere.",
        },
        "affects": {
            "good": {"tech": 1, "affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
]

EVENTS = [
    {
        "id": "1on1_no_agenda",
        "title": "1:1 With No Agenda",
        "weight": 10,
        "rounds": 1,
        "conversational": True,
        "unlock": {},
        "story": "Your manager puts a 30-minute 1:1 on your calendar. The notes field contains only a smiley face. No agenda. No explanation.",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "You still proactively organize your progress and asks so the meeting produces something concrete.",
            "neutral": "The conversation stays calm but lands with no clear result.",
            "bad": "Your complaints lose focus, your messaging is messy, or you leave the manager more worried about your state.",
        },
        "affects": {
            "good": {"visibility": 1, "affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "deadline_compressed",
        "title": "Deadline Compressed",
        "weight": 10,
        "rounds": 1,
        "unlock": {},
        "story": "The CEO sends a company-wide email announcing that a project will debut earlier to 'show Hooli's execution muscle.' Your project is on the list. The original schedule just lost six weeks.",
        "perf_review": {
            "eligible": True,
            "achievements": [
                {
                    "hook": "When the schedule was suddenly cut down, you re-scoped the work and protected the core delivery",
                    "framings": {
                        "A": "Emphasize that you reordered priorities under pressure and preserved the most critical outcome.",
                        "B": "Emphasize that you made the risk and constraints explicit early instead of letting schedule pressure explode at the last moment.",
                    },
                }
            ],
        },
        "rubric": {
            "good": "You coordinate scope and risk clearly and preserve the core delivery.",
            "neutral": "You barely keep up with the pace and the overall performance is ordinary.",
            "bad": "You fail to manage risk proactively, causing delay or a drop in team trust.",
        },
        "affects": {
            "good": {"visibility": 1, "tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "teammate_no_handoff",
        "title": "Teammate Out, No Handoff",
        "weight": 10,
        "rounds": 1,
        "conversational": True,
        "unlock": {},
        "story": "A key teammate suddenly goes on leave. Their Slack status says 'Out, back next week.' There is no handoff, no explanation, and they were in meetings yesterday. The work they owned is now sitting on your Jira board.",
        "perf_review": {
            "eligible": True,
            "achievements": [
                {
                    "hook": "You caught the work that suddenly landed on you, rebuilt the missing context, and stabilized delivery",
                    "framings": {
                        "A": "Emphasize that you proactively rebuilt the missing context instead of waiting for someone else to organize the problem first.",
                        "B": "Emphasize that you held stakeholders and delivery rhythm together under broken information flow instead of letting the situation get messier.",
                    },
                }
            ],
        },
        "rubric": {
            "good": "You rebuild the missing context quickly, sync stakeholders, and stabilize delivery.",
            "neutral": "The handoff succeeds but the efficiency is ordinary and the impact stays manageable.",
            "bad": "The takeover becomes disorderly and lost context damages schedule or quality.",
        },
        "affects": {
            "good": {"affinity": 1, "visibility": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "rto_badge_flagged",
        "title": "RTO Badge Flagged",
        "weight": 8,
        "rounds": 1,
        "unlock": {},
        "story": "The HR system sends a compliance alert asking you to explain last week's office badge records. You were in the office four days, but on the third day you only stayed in the first-floor cafe for twenty minutes before leaving. The system says that day does not count.",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "You calmly clarify the facts and align with your manager on an executable response.",
            "neutral": "You close it out with low risk, but do not improve the mechanism for next time.",
            "bad": "The communication loses focus or becomes emotional and the issue escalates.",
        },
        "affects": {
            "good": {"affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "reorg",
        "title": "Reorg",
        "weight": 3,
        "rounds": 1,
        "unlock": {},
        "story": "Friday, 4:30 PM. The whole company gets a reorg announcement. Your team is split in half, and your half is folded into a new org called Platform Synergy Initiatives. Your new manager is someone you have only seen once in an all-hands meeting, and their Slack profile photo is a blurry mountain landscape.",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "You proactively sort out the new responsibility boundaries and keep delivery moving.",
            "neutral": "You get through the adjustment period smoothly, but the impact is limited.",
            "bad": "Your role becomes confused, causing cross-team friction and blocked progress.",
        },
        "affects": {
            "good": {"visibility": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "layoff_wave",
        "title": "Layoff Wave",
        "weight": 3,
        "rounds": 1,
        "unlock": {},
        "story": "Company-wide email subject line: 'Building a New Chapter Through Strategic Talent Transformation.' Nobody knows what that means. Some people start clearing their desks, some people refresh LinkedIn like it owes them money, and some people suddenly begin arriving at the office on time. The break room is unusually quiet today.",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "You maintain professional collaboration and stable output inside uncertainty.",
            "neutral": "You respond in a low-risk way without amplifying the chaos.",
            "bad": "Anxiety takes over and your communication or judgment at work starts slipping.",
        },
        "affects": {
            "good": {"affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
]


def _sample_names(count: int) -> list[str]:
    if count <= len(NAME_POOL):
        return random.sample(NAME_POOL, k=count)
    return [random.choice(NAME_POOL) for _ in range(count)]


def pick_cast(team_member_count: int = 3) -> tuple[dict, dict, list[dict]]:
    manager = random.choice(MANAGERS)
    buddy = random.choice(BUDDIES)
    team_member_picks = random.sample(TEAM_MEMBERS, k=min(team_member_count, len(TEAM_MEMBERS)))
    names = _sample_names(2 + len(team_member_picks))

    picked_manager = {
        "id": manager["id"],
        "name": names[0],
        "display_desc": manager["display_desc"],
        "ai_personality_desc": manager["ai_personality_desc"],
    }
    picked_buddy = {
        "id": buddy["id"],
        "name": names[1],
        "display_desc": buddy["display_desc"],
        "ai_personality_desc": buddy["ai_personality_desc"],
    }
    picked_team_members = [
        {
            "id": member["id"],
            "name": names[index + 2],
            "display_desc": member["display_desc"],
            "ai_personality_desc": member["ai_personality_desc"],
        }
        for index, member in enumerate(team_member_picks)
    ]
    return picked_manager, picked_buddy, picked_team_members


def _scene_pacing_guidance(scene: dict, current_round: int, rounds: int, scene_kind: str = "project") -> str:
    lines = [
        "[Pacing Requirements]",
        "- Round 1 should only establish the task context, constraints, and first pressure point. Do not resolve the whole situation immediately.",
        "- Middle rounds should escalate the conflict so stakeholder reactions, time pressure, or risk become visible.",
        "- The final round should show the direct consequence of this decision and the short-term state afterward, but do not act out a long tail of future process all at once.",
    ]

    if current_round == rounds:
        lines.extend(
            [
                "- This is the final round. End with declarative sentences.",
                "- Do not ask the player to choose, decide, reply, or take a position at the end. No ending question marks.",
                "- The player should feel that this mini-scene has reached a stopping point, not just abstract pressure or vague foreboding.",
                "- Show at least one immediate, observable outcome, for example: the document was sent, the manager accepted it, the reviewer challenged it, it was blocked, things were temporarily stabilized, or it went live by brute force.",
                "- If the player delivered something earlier, anchor the outcome with an external reaction if possible, such as a manager reply, a meeting reaction, a system notification, or one coworker remark.",
                "- The last sentence should read like a closing line, so the player knows this segment ends here instead of sounding like setup for yet another turn.",
                '- Bad example: "The document was sent. What do you do?"',
                '- Good example: "After the document goes out, review pressure surfaces immediately, and you know the next meeting will not be pleasant."',
            ]
        )

    if scene["id"] == "system_design_rfc":
        lines.extend(
            [
                "",
                "[System Design / RFC Specific Requirements]",
                "- The core dramatic tension is incomplete information, difficult cross-team alignment, getting the document through review, and having to answer challenges.",
                "- Do not send the RFC out too early in the first half; before submission, let the pressure, ambiguous information, or stakeholder friction take shape first.",
                "- If the RFC is submitted in the final round, that round must also show direct review-side reactions, challenges, meeting pressure, or feedback.",
                '- In this scene, "RFC submitted" is not enough for an ending by itself; the review risk must actually land on the page.',
            ]
        )

    if scene["id"] == "pip_cycle":
        lines.extend(
            [
                "",
                "[PIP Specific Requirements]",
                "- A PIP is a pressure process that unfolds across several weeks, not one meeting stretched out; every round must feel like time has advanced.",
                "- Round 2 is week one: it comes right after the PIP is announced, showing the manager's concrete demands for improvement and the player's response.",
                "- Round 3 is week two: a week-later check-in that must escalate the pressure and show signs of internal transfer attempts or outreach for other opportunities.",
                "- Round 4 is week three: the eve of the final review or HR decision. Show the pressure of the outcome approaching, but do not declare that the player is fired, successfully transferred, or retained.",
                "- If the player mentions transferring teams, another team, internal opportunities, interviews, or a transfer, this round must include at least one transfer attempt or reply, such as the HR platform, a neighboring team's Tech Lead, waiting for an update, or a vague rejection.",
                "- Do not ignore transfer intent; even if it does not succeed, it must become part of the pressure line.",
                "- The final outcome is determined by the system. Do not announce the final conclusion inside the AI response.",
            ]
        )

    if scene_kind == "event":
        lines.extend(
            [
                "",
                "[Event Specific Requirements]",
                "- The core purpose of an event is absurdity and humor, not having the player solve a multi-round cross-team problem.",
                "- The absurdity should come from the company system or situation itself. NPCs and the narrator do not need to explain or underline that it is absurd.",
                "- Do not expand an event into a process that requires multi-round investigation, cross-team alignment, or technical debugging.",
                "- The player's choices affect relationships and impressions, not technical output.",
                "- Background noise can be more exaggerated in events: company announcements, HR system notices, or all-hands invites can be twice as ridiculous.",
            ]
        )

    return "\n".join(lines)


def _input_rules_block(scene_kind: str, scene: dict, current_round: int, rounds: int) -> str:
    is_last_round = current_round == rounds
    is_conversational = scene.get("conversational", False)
    show_options = (scene_kind == "project" and (not is_conversational) and current_round == 1) or (
        scene_kind == "event" and current_round == 1
    )

    lines = ["[Input and Ending Rules]"]

    if is_last_round:
        lines.append("- Close the scene directly in the final round. Do not include options, do not ask a question, and end with declarative sentences.")
    elif show_options:
        lines.append("- End this response with A/B/C options (differences in attitude or strategy, not technical detail).")
    else:
        lines.append("- Do not include options in this round.")
        lines.append("- An NPC must ask the player a direct question at the end of this round (ending with ?), so the player has a natural starting point for the reply.")
        lines.append("- The narrator may not ask the question; it must come from an NPC inside the scene.")

    if scene_kind == "project":
        lines.append("")
        lines.append("[Project Option Rules]")
        lines.append("- Project options only appear in round 1.")
        lines.append("- Round 1 options may only be opening strategies: clarify, cut scope, align on risk, or find the right person to fill in context.")
        lines.append("- All later project rounds must end with a direct NPC question instead of more options, so the player can answer in freeform.")

    lines.append("")
    lines.append("Options must differ in attitude or strategy, not technical implementation detail; a non-SWE should still understand them.")

    return "\n".join(lines)


def build_story_system_prompt(
    player_name: str,
    manager: dict,
    buddy: dict,
    team_members: list[dict],
    scene_kind: str,
    scene: dict,
    current_round: int,
    rounds: int,
    memories: list[str],
) -> str:
    memories_block = ""
    if memories:
        bullets = "\n".join(f"- {m}" for m in memories)
        memories_block = f"\n\n[Past Records]\n{bullets}"
    team_members_block = "\n".join(
        f"- {member['name']} ({member['display_desc']}): {member['ai_personality_desc']}"
        for member in team_members
    )
    pacing_block = _scene_pacing_guidance(scene, current_round, rounds, scene_kind)
    input_rules = _input_rules_block(scene_kind, scene, current_round, rounds)

    scene_block = f"""(The following is scene information. Keep the cadence and tone of the system prompt examples, not the tone of this explanatory block.)

[Player Role]
You are a mid-level engineer (L4) at Hooli. You have been on the team for a while and are dealing with routine projects and events.
Player name: {player_name}

[Cast]
Manager: {manager["name"]} ({manager["display_desc"]}), {manager["ai_personality_desc"]}
Buddy: {buddy["name"]} ({buddy["display_desc"]}), {buddy["ai_personality_desc"]}
Team members:
{team_members_block}

[Current Scene]
Type: {"Project" if scene_kind == "project" else "Event"}
{scene["title"]} ({scene["id"]})
{scene["story"]}

[Current Round: {current_round} of {rounds}]

[Scene Rules]
- Handle only one scene (project or event)
- Keep characterization consistent
- Round {rounds} must close the scene
- If past records are relevant to the current situation, you may reference them naturally so characters remember previous interactions and consequences
- If any human NPC speaks this round and there are past records, the NPC may briefly and politely mention something the player previously did, achieved, or triggered
- When referencing past records, use them only as continuity context; do not merge the old scene with the current one
- Background noise is not a separate scene and must not take over the main thread
- Background noise is not part of scoring and must not affect state
- If the player declared a concrete action last round (for example "I go talk to QA," "I check the logs," or "I message Rachel"), that action must actually happen this round and produce feedback
- If the player tries to contact multiple stakeholders or convene an alignment meeting, some people may be absent, evasive, or unhelpful, but you must not make every key stakeholder ignore the message or provide zero usable information
- If the player schedules a meeting or asks people to align, do not make the main obstacle simply "most people did not show up"; at least key people must attend or reply, even if what they provide is limited information, political phrasing, vague promises, blame shifting, or instructions to go ask someone else
- A few people may miss the meeting or auto-decline, but do not turn the meeting into an empty room with no path forward
- Every project turn must offer at least one actionable clue, concrete blocker, escalation target, or next-step constraint so the player has some way to move
- Hooli's absurdity should show up as low-quality replies, political wording, blame shifting, or vague constraints, not as everyone disappearing and killing the main thread
- Except for 1:1 or handoff scenes, each NPC-question turn must advance to a different person or situation; the same NPC must not dominate consecutive turns

{input_rules}

{pacing_block}
"""
    return f"{BASE_SYSTEM_PROMPT}\n\n{scene_block}{memories_block}"


def build_eval_prompt(scene_kind: str, scene: dict) -> str:
    scene_label = "Project" if scene_kind == "project" else "Event"
    rounds = int(scene.get("rounds", 1))
    return f"""You are a scoring system judging the player's overall performance in this scene.

[Scene Type] {scene_label}
[Scene ID] {scene["id"]}
[Scene Length] {rounds} player turn(s)
- Good: {scene["rubric"]["good"]}
- Neutral: {scene["rubric"]["neutral"]}
- Bad: {scene["rubric"]["bad"]}

[Pacing-aware scoring]
- Judge the player against what is realistically achievable within this scene length.
- A short scene can still earn good if the player makes a realistic, high-quality move that materially advances the situation.
- Do not require full resolution if this scene length only supports triage, scoping, clarification, alignment, risk framing, or securing the next concrete step.
- For 1-turn events, good often means handling the immediate pressure well, choosing a credible stance, and creating a usable next step or clear containment.
- For 2-turn projects, good often means choosing a strong opening strategy, then converting the feedback into a concrete path, clearer ownership, narrower risk, or a more credible delivery direction.
- Only rate bad for incompleteness when the player wastes the limited turn budget, avoids the real issue, or makes the situation less workable.

[Anti-speedrun rules]
The following cases must not be rated good:
- The player's response skips the scene's core conflict and directly declares an outcome
- The player's action would be unrealistic in a real workplace, such as resolving a multi-party conflict in one sentence, bypassing process and shipping directly, or claiming completion without gathering necessary information
- The player's response has no substantive content and only declares results such as "I quickly finish every task and deliver perfectly"
- The player exploits wording loopholes in the scene to skip the core decision points with formally correct language

If the player declares a perfect outcome in one sentence, rate it bad and explain that there is no process and no supporting evidence.
If the player simply punts back to the requester without handling it, while this scene's rubric expects forward motion, rate it bad or neutral.
If the player skips the core decision without obviously causing disaster, the maximum rating is neutral.
Judging standard: in a real Hooli environment, what consequences would this response have?

Output JSON based on the conversation:
{{"rating": "good" | "neutral" | "bad", "reason": "One sentence explaining the rating"}}
Background noise (company-wide emails, Slack notices, culture ambassador messages) counts only as environment description and must not be used as scoring evidence.
Do not output any preamble, postscript, or markdown code block, and do not write sentences like "Here is the JSON requested."
Output JSON only. No explanation."""


MEMORY_PROMPT = """Below is a game-scene conversation. Summarize it in 2-3 neutral sentences.
Use third person "the player" and keep the concrete actions and outcomes."""


PERF_ARTIFACT_PROMPT = """Turn a Hooli game scene into candidate material for a performance review.

Output JSON containing:
- title: a 3-8 word self-review style achievement title; do not use Project, Event, or player
- summary: a short result summary shown to the player, using second person "you"; do not use "player"
- framing_a: one optional self-review framing angle grounded in the actual conversation; do not exaggerate
- framing_b: another optional self-review framing angle that is meaningfully different from framing_a

Rules:
- The framing must come from the actions and outcomes that actually happened, not a generic template
- If the scene result is only neutral or has obvious flaws, the framing may polish it, but it must preserve the limitations and risk; do not write it as a flawless win
- Do not use system words such as "player", "event", or "framing"
- Output JSON only. No markdown. No preamble."""
