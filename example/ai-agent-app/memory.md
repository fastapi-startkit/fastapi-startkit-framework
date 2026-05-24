                 +-------------------+
                 |   Input/Event     |
                 +-------------------+
                           |
                           v
                 +-------------------+
                 |  Memory Router    |
                 | classify memory   |
                 +-------------------+
                    |    |    |
        +-----------+    |    +-------------+
        |                |                  |
        v                v                  v

 +---------------+ +---------------+ +---------------+
 | Semantic Mem  | | Episodic Mem  | | Task Memory   |
 | facts/knowledge| | events/logs   | | goals/progress|
 +---------------+ +---------------+ +---------------+
        |                |                  |
        +----------------+------------------+
                         |
                         v
                +------------------+
                | Retrieval Layer  |
                | ranking/hybrid   |
                +------------------+
                         |
                         v
                +------------------+
                | Working Memory   |
                | active context   |
                +------------------+
                         |
                         v
                        LLM
                         |
                         v
                +------------------+
                | Reflection Layer |
                | summarization    |
                | consolidation    |
                +------------------+
