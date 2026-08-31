from pathlib import Path
import re

import chromadb
import ollama


# ============================================================
# CONFIGURATION
# ============================================================

DOCUMENTS_DIR = Path("documents")

COLLECTION_NAME = "oracle_dba_knowledge"

CHUNK_SIZE = 1200


# ============================================================
# CHROMADB
# ============================================================

client = chromadb.PersistentClient(
    path="./chroma_db"
)


# ============================================================
# DELETE OLD COLLECTION
# ============================================================

try:

    client.delete_collection(
        name=COLLECTION_NAME
    )

except Exception:

    pass


collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# AWR SECTIONS
# ============================================================

AWR_SECTIONS = [

    "Report Summary",

    "Top ADDM Findings",

    "Load Profile",

    "Instance Efficiency Percentages",

    "Top 10 Foreground Events by Total Wait Time",

    "Foreground Wait Class",

    "Wait Events",

    "SQL Statistics",

    "IO Stats",

    "Tablespace IO Stats",

    "File IO Stats",

    "Instance Activity Statistics",

    "Active Session History",

    "ADDM Report",

    "Segment Statistics",

    "Memory Statistics",

    "Undo Statistics",

    "Undo Segment Summary",

    "Table Statistics",

    "Index Statistics",

    "Advisory Statistics",

]


# ============================================================
# DETECT AWR SECTION
# ============================================================

def detect_section(
    line,
    current_section
):

    cleaned = line.strip()

    if not cleaned:

        return current_section


    for section in AWR_SECTIONS:

        if cleaned.lower() == section.lower():

            return section


        if section.lower() in cleaned.lower():

            return section


    return current_section


# ============================================================
# NORMAL TEXT CHUNKING
# ============================================================

def split_large_text(
    text,
    chunk_size=CHUNK_SIZE
):

    chunks = []


    for start in range(
        0,
        len(text),
        chunk_size
    ):

        chunk = text[
            start:start + chunk_size
        ].strip()


        if chunk:

            chunks.append(
                chunk
            )


    return chunks


# ============================================================
# EXTRACT ADDM FINDINGS
# ============================================================

def extract_addm_findings(
    text
):

    findings = []


    pattern = re.compile(

        r"(Finding\s+\d+:.*?)(?="
        r"Finding\s+\d+:|"
        r"Back to Top|"
        r"$)",

        re.IGNORECASE |
        re.DOTALL

    )


    matches = pattern.findall(
        text
    )


    for match in matches:

        cleaned = match.strip()


        if len(cleaned) > 50:

            findings.append(
                cleaned
            )


    return findings


# ============================================================
# CREATE AWR CHUNKS
# ============================================================

def create_awrr_chunks(
    text
):

    chunks = []


    # ========================================================
    # FIRST:
    # Extract ADDM findings.
    #
    # Finding 1, 3, 4 and 5 stay together.
    #
    # Finding 2 contains potentially huge SQL text,
    # so Finding 2 is allowed to split.
    # ========================================================

    addm_findings = extract_addm_findings(
        text
    )


    for index, finding in enumerate(
        addm_findings
    ):

        finding_number = index + 1


        # ----------------------------------------------------
        # First line contains finding name
        # ----------------------------------------------------

        first_line = (
            finding
            .splitlines()[0]
            .strip()
        )


        finding_name = first_line


        # ----------------------------------------------------
        # Finding 2 can be very large because it contains
        # SQL statements.
        #
        # Other findings stay as complete logical units.
        # ----------------------------------------------------

        if finding_number == 2:

            finding_chunks = split_large_text(
                finding
            )

        else:

            finding_chunks = [
                finding
            ]


        # ----------------------------------------------------
        # Store ADDM chunks
        # ----------------------------------------------------

        for sub_index, chunk in enumerate(
            finding_chunks
        ):

            chunks.append(

                {

                    "section":
                        "ADDM Finding",

                    "subsection":
                        f"Finding {finding_number}",

                    "finding_number":
                        str(finding_number),

                    "finding_name":
                        finding_name,

                    "text":
                        chunk

                }

            )


    # ========================================================
    # SECOND:
    # Process the rest of the AWR.
    # ========================================================

    current_section = "General"

    current_lines = []


    for line in text.splitlines():

        new_section = detect_section(
            line,
            current_section
        )


        # ----------------------------------------------------
        # Section changed
        # ----------------------------------------------------

        if new_section != current_section:


            if current_lines:

                section_text = (
                    "\n".join(
                        current_lines
                    )
                    .strip()
                )


                if section_text:

                    for chunk in split_large_text(
                        section_text
                    ):

                        chunks.append(

                            {

                                "section":
                                    current_section,

                                "subsection":
                                    "",

                                "finding_number":
                                    "",

                                "finding_name":
                                    "",

                                "text":
                                    chunk

                            }

                        )


            current_section = new_section

            current_lines = []


        current_lines.append(
            line
        )


    # ========================================================
    # FINAL SECTION
    # ========================================================

    if current_lines:

        section_text = (
            "\n".join(
                current_lines
            )
            .strip()
        )


        if section_text:

            for chunk in split_large_text(
                section_text
            ):

                chunks.append(

                    {

                        "section":
                            current_section,

                        "subsection":
                            "",

                        "finding_number":
                            "",

                        "finding_name":
                            "",

                        "text":
                            chunk

                    }

                )


    return chunks


# ============================================================
# NORMAL NON-AWR CHUNKS
# ============================================================

def create_normal_chunks(
    text
):

    chunks = []


    for chunk in split_large_text(
        text
    ):

        chunks.append(

            {

                "section":
                    "General",

                "subsection":
                    "",

                "finding_number":
                    "",

                "finding_name":
                    "",

                "text":
                    chunk

            }

        )


    return chunks


# ============================================================
# INGEST DOCUMENTS
# ============================================================

for file_path in sorted(
    DOCUMENTS_DIR.glob("*.txt")
):


    print(
        f"\nReading: {file_path.name}"
    )


    text = file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )


    print(
        f"Characters: {len(text)}"
    )


    # ========================================================
    # AWR
    # ========================================================

    if file_path.name.startswith(
        "awrrpt_"
    ):

        chunks = create_awrr_chunks(
            text
        )

        document_type = "AWR"


    # ========================================================
    # NORMAL DBA DOCUMENT
    # ========================================================

    else:

        chunks = create_normal_chunks(
            text
        )

        document_type = "Oracle DBA"


    print(
        f"Created {len(chunks)} chunks"
    )


    # ========================================================
    # EMBED + STORE
    # ========================================================

    for index, item in enumerate(
        chunks
    ):


        chunk_text = item[
            "text"
        ]


        section = item[
            "section"
        ]


        subsection = item[
            "subsection"
        ]


        finding_number = item.get(
            "finding_number",
            ""
        )


        finding_name = item.get(
            "finding_name",
            ""
        )


        # ====================================================
        # EMBEDDING TEXT
        #
        # Metadata is included in the embedding so that
        # semantic retrieval understands the finding context.
        # ====================================================

        embedding_text = (

            f"Document type: "
            f"{document_type}\n"

            f"Source: "
            f"{file_path.name}\n"

            f"Section: "
            f"{section}\n"

            f"Subsection: "
            f"{subsection}\n"

            f"Finding number: "
            f"{finding_number}\n"

            f"Finding name: "
            f"{finding_name}\n\n"

            f"{chunk_text}"

        )


        # ====================================================
        # OLLAMA EMBEDDING
        # ====================================================

        response = ollama.embed(

            model="nomic-embed-text",

            input=embedding_text

        )


        embedding = response[
            "embeddings"
        ][0]


        # ====================================================
        # CHROMADB UPSERT
        # ====================================================

        collection.upsert(

            ids=[

                f"{file_path.stem}-{index}"

            ],

            documents=[

                chunk_text

            ],

            embeddings=[

                embedding

            ],

            metadatas=[

                {

                    "source":
                        file_path.name,

                    "document_type":
                        document_type,

                    "section":
                        section,

                    "subsection":
                        subsection,

                    "finding_number":
                        finding_number,

                    "finding_name":
                        finding_name,

                    "chunk":
                        index

                }

            ]

        )


        # ====================================================
        # PROGRESS
        # ====================================================

        print(

            f"  Stored chunk {index}"

            f" | Section: {section}"

            + (

                f" | {subsection}"

                if subsection

                else ""

            )

        )


# ============================================================
# COMPLETE
# ============================================================

print(
    "\n--------------------------------"
)

print(
    "Ingestion complete!"
)

print(
    "Total vectors:",
    collection.count()
)

print(
    "--------------------------------"
)