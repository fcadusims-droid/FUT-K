# What Consensus means

A live match is described by many imperfect sources — stat feeds, live text,
crowds, commentators. FUT-K's design treats each one as a biased witness and
**reconciles them into one diagnosis with an agreement level**:

    Feed A:      dangerous attack
    Feed B:      ordinary attack
    Chat:        almost a goal!
    Commentary:  great save
    → Consensus: "chance created", agreement 92%

Two rules:

1. **Sources earn their weight.** A source's influence comes from its
   historical accuracy, not its fame. A pundit who is usually wrong weighs
   less than a feed that is usually right.
2. **Disagreement is information, not noise.** When the data says "balanced"
   but the crowd says "disaster", FUT-K does not pick a side — it lowers its
   confidence and surfaces the divergence. That gap between perception and
   reality is one of the most interesting things the engine can show you.

This is no longer just a design idea: FUT-K's **Data Fusion Layer** reconciles
three real, independent providers (StatsBomb, football-data.co.uk,
openfootball) over historical matches — deterministic majority voting with
provenance and recorded dissent for every fused value. The replay app itself
still reads from a single curated source; the consensus machinery becomes
fully live when real-time multi-source feeds are connected.
