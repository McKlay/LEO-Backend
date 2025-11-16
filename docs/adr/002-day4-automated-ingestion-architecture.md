# Day 4 KB Enhancement: Automated Ingestion Architecture

## System Overview

```mermaid
graph TB
    subgraph "Input: kb/docs/ (10 documents)"
        A1[PD-No-442.txt<br/>Labor Code<br/>2061 lines]
        A2[PD-No-851.txt<br/>13th Month Pay]
        A3[DOLE-Handbook.txt<br/>Benefits Guide<br/>2705 lines]
        A4[Other 7 docs]
    end

    subgraph "Ingestion Pipeline"
        B1[TextFileLoader<br/>UTF-8 → latin-1 fallback]
        B2[LegalDocumentChunker<br/>Article/Section-based]
        B3[GPT-4o-mini<br/>Summary Generator]
        B4[OpenAI Embeddings<br/>text-embedding-3-small]
        B5[Metadata Enrichment<br/>source, type, URL]
    end

    subgraph "Supabase Database"
        C1[(labor_law_sources)]
        C2[(labor_law_sections)]
        C3[HNSW Index<br/>Vector Search]
        C4[GIN Index<br/>Full-Text Search]
        C5[B-tree Indexes<br/>Article Lookup]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1
    
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> B5
    
    B5 --> C1
    B5 --> C2
    C2 --> C3
    C2 --> C4
    C2 --> C5

    style A1 fill:#e1f5ff
    style A3 fill:#e1f5ff
    style B3 fill:#fff3cd
    style B4 fill:#fff3cd
    style C2 fill:#d4edda
    style C3 fill:#d4edda
    style C4 fill:#d4edda
```

## Chunking Strategy by Document Type

```mermaid
flowchart LR
    subgraph "Statute (e.g., PD-442)"
        S1[Full Document] --> S2{Parse Structure}
        S2 --> S3[Book I]
        S2 --> S4[Book II]
        S3 --> S5[Title → Chapter → Article]
        S5 --> S6{Article<br/>Word Count}
        S6 -->|<300 words| S7[Single Chunk]
        S6 -->|>300 words| S8[Multi-Chunk<br/>with 20-word overlap]
    end

    subgraph "Handbook (e.g., DOLE Handbook)"
        H1[Full Document] --> H2{Parse Sections}
        H2 --> H3[Section 1: Minimum Wage]
        H2 --> H4[Section 2: Holiday Pay]
        H3 --> H5{Section<br/>Word Count}
        H5 -->|<300 words| H6[Single Chunk]
        H5 -->|>300 words| H7[Subsection Chunks<br/>A, B, C, D]
    end

    subgraph "Rules (e.g., NLRC Rules)"
        R1[Full Document] --> R2{Parse Rules}
        R2 --> R3[Rule I]
        R2 --> R4[Rule II]
        R3 --> R5[Section 1, 2, 3...]
        R5 --> R6[Individual Chunks]
    end

    style S7 fill:#d4edda
    style S8 fill:#fff3cd
    style H6 fill:#d4edda
    style H7 fill:#fff3cd
    style R6 fill:#d4edda
```

## Metadata Structure per Chunk

```mermaid
classDiagram
    class Chunk {
        +String id
        +String content (full_text)
        +String summary (GPT-4o-mini generated)
        +Vector~1536~ embedding
        +Metadata metadata
    }

    class Metadata {
        +String source
        +String doc_type
        +String article_number
        +String article_title
        +String book
        +String title_name
        +String chapter
        +String[] keywords
        +String url
        +String year
        +String short_name
    }

    class VectorIndex {
        +HNSW m=16
        +HNSW ef_construction=64
        +Distance cosine
    }

    class FullTextIndex {
        +GIN to_tsvector
        +Language english
    }

    Chunk "1" --> "1" Metadata
    Chunk "1" --> "1" VectorIndex
    Chunk "1" --> "1" FullTextIndex
```

## Ingestion Workflow

```mermaid
sequenceDiagram
    participant CLI as sync_to_vectorstore CLI
    participant Loader as TextFileLoader
    participant Chunker as LegalDocumentChunker
    participant LLM as GPT-4o-mini
    participant Embed as OpenAI Embeddings
    participant DB as Supabase (labor_law_sections)

    CLI->>Loader: Load PD-No-442.txt
    Loader->>Loader: UTF-8 decode with fallback
    Loader-->>CLI: 2061 lines content

    CLI->>Chunker: chunk_document(content, metadata)
    Chunker->>Chunker: Detect Articles (regex)
    Chunker->>Chunker: Split by Articles
    Chunker->>Chunker: Check word count per chunk
    Chunker-->>CLI: 85 chunks (avg 245 words)

    loop For each chunk
        CLI->>LLM: Generate summary (if >100 words)
        LLM-->>CLI: 2-3 sentence summary
        CLI->>Embed: Generate embedding
        Embed-->>CLI: 1536-dim vector
    end

    CLI->>DB: Batch upsert 85 documents
    DB->>DB: Insert into labor_law_sections
    DB->>DB: Update HNSW index
    DB->>DB: Update GIN index
    DB-->>CLI: Success (85 chunks, 12,450 tokens)

    CLI->>CLI: Log statistics
```

## Multi-Strategy Retrieval

```mermaid
flowchart TB
    A[User Query:<br/>'What is 13th month pay?'] --> B{Query Analysis<br/>GPT-4o-mini}
    
    B --> C{Needs<br/>Clarification?}
    
    C -->|Yes: Vague| D[Return Clarification<br/>with 3-4 follow-ups<br/>STOP pipeline]
    
    C -->|No: Clear| E{Parse Query}
    
    E --> F[Extract Article #:<br/>None]
    E --> G[Extract Keywords:<br/>'13th month', 'pay']
    E --> H[Extract Concepts:<br/>'employee benefits', 'wages']
    
    F --> I{Has Article?}
    I -->|Yes| J[Direct Article Lookup<br/>labor_law_sections.article_number]
    I -->|No| K[Skip Direct Lookup]
    
    G --> L[Keyword Search<br/>PostgreSQL FTS + GIN]
    
    H --> M[Semantic Search<br/>Vector similarity + HNSW]
    
    J --> N[Merge & Rank Results]
    K --> N
    L --> N
    M --> N
    
    N --> O{Results<br/>Found?}
    
    O -->|Yes| P[Top 5 chunks:<br/>PD-851 full text<br/>DOLE Handbook Section 13<br/>+ 3 more]
    
    O -->|No| Q[Fallback:<br/>Suggest related topics]
    
    P --> R[Single-Step Grounding<br/>Build rich context prompt]
    
    R --> S[GPT-4 Turbo Streaming<br/>Generate response with citations]
    
    S --> T[Stream to user<br/>SSE format]

    style D fill:#fff3cd
    style P fill:#d4edda
    style S fill:#e1f5ff
    style T fill:#e1f5ff
```

## Expected Database State After Day 4
```mermaid
erDiagram
    labor_law_sources ||--o{ labor_law_sections : contains

    labor_law_sources {
        uuid id PK
        varchar source_type
        text title
        varchar reference
        text url
        text notes "Total sources: statutes, handbooks, rules"
    }

    labor_law_sections {
        uuid id PK
        uuid source_id FK
        varchar article_number
        text article_title
        text full_text
        text summary
        text[] keywords
        jsonb metadata
        vector_1536 embedding
        varchar book
        varchar title_name
        varchar chapter
        text stats "150-300 chunks from 10 documents; all have embeddings; most have summaries (>100 words)"
    }
```

## Performance Optimization Stack

```mermaid
graph LR
    subgraph "Layer 1: Smart Routing"
        A1[Query Analysis] --> A2{Article mentioned?}
        A2 -->|Yes| A3[Direct Lookup<br/>~200ms]
        A2 -->|No| A4[Continue to Layer 2]
    end

    subgraph "Layer 2: Parallel Retrieval"
        A4 --> B1[Keyword Search<br/>GIN Index<br/>~800ms]
        A4 --> B2[Vector Search<br/>HNSW Index<br/>~2000ms]
    end

    subgraph "Layer 3: Caching"
        B1 --> C1[Check Embedding Cache]
        B2 --> C1
        C1 -->|Hit 30%| C2[Skip API Call<br/>Save ~500ms]
        C1 -->|Miss 70%| C3[OpenAI API<br/>~500ms]
    end

    subgraph "Layer 4: Connection Pooling"
        C2 --> D1[Reuse DB Connection<br/>Save ~300ms]
        C3 --> D1
    end

    subgraph "Result"
        D1 --> E1[Combined Results<br/>Ranked by relevance]
        E1 --> E2[Total: <2.5s retrieval]
    end

    style A3 fill:#d4edda
    style C2 fill:#d4edda
    style E2 fill:#d4edda
```

---

**Key Insights**:

1. **Automated Chunking**: Adapts to document structure (Article/Section/Rule)
2. **Smart Summarization**: Only for chunks >100 words to save costs
3. **Multi-Index Strategy**: HNSW (semantic) + GIN (keyword) + B-tree (direct)
4. **Performance Stack**: Caching + pooling + parallel queries = <2.5s retrieval
5. **Scalable**: Can easily add more documents by updating `DOCUMENT_REGISTRY`

---

**Last Updated**: November 13, 2025
