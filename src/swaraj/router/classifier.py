"""Task classification for router decision-making.

Analyzes task descriptions to extract characteristics that inform routing:
- Does the task require code generation?
- Does the task require OCR/image understanding?
- Does the task require summarization?
- What is the expected complexity?

This module uses deterministic keyword/pattern matching rather than ML
to ensure reproducibility and auditability in air-gapped environments.
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass(frozen=True)
class TaskCharacteristics:
    """Characteristics extracted from a task description.

    Attributes:
        code_required: True if task involves code generation/analysis
        ocr_required: True if task involves image/PDF/text extraction
        summarization_required: True if task involves summarization
        structured_output_required: True if task requires JSON/table output
        domain: Detected domain (e.g., 'refinery', 'industrial', 'general')
        complexity: Estimated complexity level (1-5)
        raw_keywords: List of detected keywords that informed classification
    """

    code_required: bool = False
    ocr_required: bool = False
    summarization_required: bool = False
    structured_output_required: bool = False
    domain: str = "general"
    complexity: int = 1
    raw_keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "code_required": self.code_required,
            "ocr_required": self.ocr_required,
            "summarization_required": self.summarization_required,
            "structured_output_required": self.structured_output_required,
            "domain": self.domain,
            "complexity": self.complexity,
            "raw_keywords": list(self.raw_keywords),
        }


class TaskClassifier:
    """Classifies task descriptions into characteristic categories.

    Uses deterministic pattern matching to ensure:
    - Reproducible results for identical inputs
    - Auditability (can trace which patterns matched)
    - No hidden ML model dependencies

    The classifier identifies:
    - Code-related tasks (programming, scripts, functions)
    - OCR-related tasks (images, PDFs, scanned documents, extraction)
    - Summarization tasks (summary, brief, overview)
    - Structured output tasks (JSON, table, Excel, spreadsheet)
    - Domain context (refinery, industrial, inspection)
    """

    # Deterministic keyword patterns for classification
    CODE_PATTERNS = [
        r"\bcode\b",
        r"\bfunction\b",
        r"\bdef\s+\w+\s*\(",
        r"\bpython\b",
        r"\bscript\b",
        r"\bprogram\b",
        r"\balgorithm\b",
        r"\bregex\b",
        r"\bparse\b",
    ]

    OCR_PATTERNS = [
        r"\bimage\b",
        r"\bscan\b",
        r"\bpdf\b",
        r"\bdocument\b",
        r"\bextract\b",
        r"\bocr\b",
        r"\bgauge\b",
        r"\bp&id\b",
        r"\bpiping\b",
        r"\bdiagram\b",
        r"\bscreenshot\b",
        r"\bphoto\b",
        r"\bpicture\b",
    ]

    SUMMARY_PATTERNS = [
        r"\bsummarize\b",
        r"\bsummary\b",
        r"\bbrief\b",
        r"\boverview\b",
        r"\bkey points\b",
        r"\bhighlights?\b",
        r"\bcondense\b",
        r"\babridge\b",
    ]

    STRUCTURED_PATTERNS = [
        r"\bjson\b",
        r"\btable\b",
        r"\bexcel\b",
        r"\bspreadsheet\b",
        r"\bcsv\b",
        r"\bstructured\b",
        r"\bfield\b",
        r"\bcolumn\b",
        r"\brow\b",
    ]

    DOMAIN_PATTERNS = {
        "refinery": [
            r"\brefinery\b",
            r"\brefining\b",
            r"\bpetroleum\b",
            r"\bpetrochemical\b",
            r"\bcrude\b",
            r"\bdistillation\b",
        ],
        "industrial": [
            r"\bindustrial\b",
            r"\bplant\b",
            r"\bfactory\b",
            r"\bmanufacturing\b",
            r"\bprocess\b",
            r"\bequipment\b",
        ],
        "inspection": [
            r"\binspection\b",
            r"\binspector\b",
            r"\baudit\b",
            r"\bcompliance\b",
            r"\bfinding\b",
            r"\bviolation\b",
        ],
    }

    COMPLEXITY_INDICATORS = {
        5: [r"\bcomplex\b", r"\bintricate\b", r"\bmulti-step\b", r"\badvanced\b"],
        4: [r"\bdetailed\b", r"\bcomprehensive\b", r"\bthorough\b"],
        3: [r"\banalyze\b", r"\bevaluate\b", r"\bcompare\b"],
        2: [r"\bsimple\b", r"\bbasic\b", r"\bquick\b"],
        1: [],  # Default
    }

    def classify(self, task_description: str) -> TaskCharacteristics:
        """Classify a task description into characteristics.

        Args:
            task_description: The task description text to analyze

        Returns:
            TaskCharacteristics with detected attributes

        The classification is deterministic - same input always produces same output.
        """
        text_lower = task_description.lower()
        keywords: list[str] = []

        # Check code patterns
        code_required = False
        for pattern in self.CODE_PATTERNS:
            if re.search(pattern, text_lower):
                code_required = True
                keywords.append(f"code:{pattern}")
                break

        # Check OCR patterns
        ocr_required = False
        for pattern in self.OCR_PATTERNS:
            if re.search(pattern, text_lower):
                ocr_required = True
                keywords.append(f"ocr:{pattern}")
                break

        # Check summary patterns
        summarization_required = False
        for pattern in self.SUMMARY_PATTERNS:
            if re.search(pattern, text_lower):
                summarization_required = True
                keywords.append(f"summary:{pattern}")
                break

        # Check structured output patterns
        structured_required = False
        for pattern in self.STRUCTURED_PATTERNS:
            if re.search(pattern, text_lower):
                structured_required = True
                keywords.append(f"structured:{pattern}")
                break

        # Detect domain
        domain = "general"
        for domain_name, patterns in self.DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    domain = domain_name
                    keywords.append(f"domain:{domain_name}")
                    break
            if domain != "general":
                break

        # Estimate complexity
        complexity = 1
        for level, patterns in sorted(self.COMPLEXITY_INDICATORS.items(), reverse=True):
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    complexity = level
                    keywords.append(f"complexity:{level}")
                    break
            if complexity != 1:
                break

        return TaskCharacteristics(
            code_required=code_required,
            ocr_required=ocr_required,
            summarization_required=summarization_required,
            structured_output_required=structured_required,
            domain=domain,
            complexity=complexity,
            raw_keywords=tuple(sorted(keywords)),
        )

    def get_required_capabilities(
        self, characteristics: TaskCharacteristics
    ) -> list[str]:
        """Get list of required capabilities based on task characteristics.

        Args:
            characteristics: The classified task characteristics

        Returns:
            List of capability names required for this task
        """
        capabilities = []

        if characteristics.code_required:
            capabilities.append("code")

        if characteristics.ocr_required:
            capabilities.append("ocr_extract")

        if characteristics.summarization_required:
            capabilities.append("summary")

        # Default to summary if no specific capability detected
        if not capabilities:
            capabilities.append("summary")

        return capabilities
