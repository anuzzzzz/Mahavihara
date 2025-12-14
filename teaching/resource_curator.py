"""
Resource Curator - External learning resource discovery.

"ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp."

Features:
    - YouTube video search with timestamp extraction
    - Web search for articles/tutorials (via Tavily)
    - Pre-vetted resource database
    - Quality scoring and filtering by trusted sources
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Optional Tavily import
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


@dataclass
class LearningResource:
    """A curated learning resource."""
    id: str
    title: str
    url: str
    source_type: str  # "youtube", "article", "interactive", "practice"
    concept_id: str
    difficulty: int  # 1-3
    duration_minutes: Optional[int] = None
    quality_score: float = 0.8  # 0-1
    description: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None  # For YouTube: "2:34"
    why_recommended: str = ""


# Trusted sources with quality weights
TRUSTED_SOURCES = {
    "youtube.com": {
        "weight": 0.9,
        "channels": {
            "3blue1brown": 0.99,
            "khan academy": 0.95,
            "professor leonard": 0.92,
            "mathispower4u": 0.88,
            "organic chemistry tutor": 0.90,
        }
    },
    "khanacademy.org": {"weight": 0.95},
    "brilliant.org": {"weight": 0.90},
    "mathworld.wolfram.com": {"weight": 0.85},
    "mit.edu": {"weight": 0.92},
}


# Pre-curated high-quality resources (fallback when search unavailable)
CURATED_RESOURCES = {
    "vectors": [
        {
            "id": "yt_3b1b_vectors",
            "title": "Vectors | Chapter 1, Essence of linear algebra",
            "url": "https://youtube.com/watch?v=fNk_zzaMoSs",
            "source_type": "youtube",
            "difficulty": 1,
            "duration_minutes": 10,
            "quality_score": 0.98,
            "description": "3Blue1Brown's visual introduction to vectors. Beautiful animations that build intuition.",
            "tags": ["visual", "beginner", "animation", "3b1b"],
            "why_recommended": "Best visual introduction to vectors - builds intuition before formulas"
        },
        {
            "id": "khan_vectors",
            "title": "Vector intro for linear algebra",
            "url": "https://www.khanacademy.org/math/linear-algebra/vectors-and-spaces",
            "source_type": "interactive",
            "difficulty": 1,
            "duration_minutes": 30,
            "quality_score": 0.90,
            "description": "Khan Academy's complete unit with practice problems and immediate feedback.",
            "tags": ["practice", "interactive", "comprehensive"],
            "why_recommended": "Practice problems with instant feedback - test your understanding"
        },
    ],
    "matrix_ops": [
        {
            "id": "yt_3b1b_matrix",
            "title": "Linear transformations and matrices | Chapter 3",
            "url": "https://youtube.com/watch?v=kYB8IZa5AuE",
            "source_type": "youtube",
            "difficulty": 2,
            "duration_minutes": 11,
            "quality_score": 0.98,
            "description": "Understanding matrices as transformations. This will change how you see matrices forever.",
            "tags": ["visual", "transformation", "intuition", "3b1b"],
            "why_recommended": "See matrices as transformations, not just grids of numbers"
        },
        {
            "id": "yt_3b1b_matmul",
            "title": "Matrix multiplication as composition | Chapter 4",
            "url": "https://youtube.com/watch?v=XkY2DOUCWMU",
            "source_type": "youtube",
            "difficulty": 2,
            "duration_minutes": 10,
            "quality_score": 0.98,
            "description": "Why matrix multiplication is defined the way it is.",
            "tags": ["visual", "composition", "3b1b"],
            "why_recommended": "Understand WHY matrix multiplication works the way it does"
        },
        {
            "id": "yt_mathispower_matrix",
            "title": "Matrix Multiplication Made Easy",
            "url": "https://youtube.com/watch?v=2spTnAiQg4M",
            "source_type": "youtube",
            "difficulty": 1,
            "duration_minutes": 8,
            "quality_score": 0.85,
            "description": "Step-by-step matrix multiplication with lots of examples.",
            "tags": ["tutorial", "examples", "beginner"],
            "why_recommended": "Step-by-step calculation practice"
        },
    ],
    "determinants": [
        {
            "id": "yt_3b1b_determinant",
            "title": "The determinant | Chapter 6, Essence of linear algebra",
            "url": "https://youtube.com/watch?v=Ip3X9LOh2dk",
            "source_type": "youtube",
            "difficulty": 2,
            "duration_minutes": 10,
            "quality_score": 0.98,
            "description": "What determinants REALLY mean geometrically. The 'aha moment' video.",
            "tags": ["visual", "geometric", "intuition", "3b1b"],
            "why_recommended": "Visual meaning - determinant as scaling factor"
        },
        {
            "id": "yt_organic_det",
            "title": "Determinants - How to Calculate (2x2, 3x3)",
            "url": "https://youtube.com/watch?v=21LGVGdpJLE",
            "source_type": "youtube",
            "difficulty": 1,
            "duration_minutes": 12,
            "quality_score": 0.88,
            "description": "Clear step-by-step calculation methods for 2x2 and 3x3 determinants.",
            "tags": ["tutorial", "calculation", "step-by-step"],
            "why_recommended": "Learn the mechanical calculation"
        },
    ],
    "inverse_matrix": [
        {
            "id": "yt_3b1b_inverse",
            "title": "Inverse matrices, column space and null space | Chapter 7",
            "url": "https://youtube.com/watch?v=uQhTuRlWMxw",
            "source_type": "youtube",
            "difficulty": 2,
            "duration_minutes": 12,
            "quality_score": 0.98,
            "description": "Deep understanding of what matrix inverse means and when it exists.",
            "tags": ["visual", "comprehensive", "3b1b"],
            "why_recommended": "When and why inverses exist"
        },
        {
            "id": "khan_inverse",
            "title": "Inverse of a 2x2 matrix",
            "url": "https://www.khanacademy.org/math/algebra-home/alg-matrices/alg-intro-to-matrix-inverses",
            "source_type": "interactive",
            "difficulty": 1,
            "duration_minutes": 20,
            "quality_score": 0.90,
            "description": "Learn the formula with practice problems.",
            "tags": ["practice", "formula", "interactive"],
            "why_recommended": "Practice the 2x2 inverse formula"
        },
    ],
    "eigenvalues": [
        {
            "id": "yt_3b1b_eigen",
            "title": "Eigenvectors and eigenvalues | Chapter 14, Essence of linear algebra",
            "url": "https://youtube.com/watch?v=PFDu9oVAE-g",
            "source_type": "youtube",
            "difficulty": 2,
            "duration_minutes": 17,
            "quality_score": 0.99,
            "description": "The most intuitive explanation of eigenvalues you'll find anywhere.",
            "tags": ["visual", "intuition", "advanced", "3b1b"],
            "why_recommended": "The BEST eigenvalue explanation - pure intuition"
        },
        {
            "id": "yt_maththebeautiful_eigen",
            "title": "Eigenvalues and Eigenvectors - Explained Visually",
            "url": "https://youtube.com/watch?v=vs2sRvSzA3o",
            "source_type": "youtube",
            "difficulty": 3,
            "duration_minutes": 15,
            "quality_score": 0.85,
            "description": "Another perspective with clear visual examples.",
            "tags": ["visual", "examples", "alternative"],
            "why_recommended": "Alternative visual explanation"
        },
    ],
}


class ResourceCurator:
    """
    Curates and recommends external learning resources.

    Combines:
    - Pre-vetted resource database (always available)
    - Real-time web search via Tavily (when API key available)
    - Quality filtering based on trusted sources
    """

    def __init__(
        self,
        resources_path: str = "data/resources/curated_links.json",
        tavily_api_key: Optional[str] = None
    ):
        self.resources_path = Path(resources_path)
        self.resources: Dict[str, LearningResource] = {}
        self.concept_resources: Dict[str, List[str]] = {}  # concept_id -> [resource_ids]

        # Initialize Tavily client if available
        self.tavily_client = None
        api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        if api_key and TAVILY_AVAILABLE:
            try:
                self.tavily_client = TavilyClient(api_key=api_key)
            except Exception as e:
                print(f"Could not initialize Tavily: {e}")

        self._load_resources()

    def _load_resources(self):
        """Load pre-vetted resources from JSON or use defaults."""
        # First load from file if exists
        if self.resources_path.exists():
            try:
                with open(self.resources_path, 'r') as f:
                    data = json.load(f)
                self._process_resource_data(data.get("resources", []))
            except Exception as e:
                print(f"Error loading resources: {e}")

        # Supplement with curated defaults
        self._load_curated_defaults()

    def _process_resource_data(self, resources_data: List[Dict]):
        """Process resource data into LearningResource objects."""
        for r_data in resources_data:
            resource = LearningResource(
                id=r_data["id"],
                title=r_data["title"],
                url=r_data["url"],
                source_type=r_data["source_type"],
                concept_id=r_data["concept_id"],
                difficulty=r_data.get("difficulty", 2),
                duration_minutes=r_data.get("duration_minutes"),
                quality_score=r_data.get("quality_score", 0.8),
                description=r_data.get("description", ""),
                tags=r_data.get("tags", []),
                timestamp=r_data.get("timestamp"),
                why_recommended=r_data.get("why_recommended", "")
            )
            self._add_resource(resource)

    def _load_curated_defaults(self):
        """Load curated default resources."""
        for concept_id, resources in CURATED_RESOURCES.items():
            for r_data in resources:
                resource = LearningResource(
                    id=r_data["id"],
                    title=r_data["title"],
                    url=r_data["url"],
                    source_type=r_data["source_type"],
                    concept_id=concept_id,
                    difficulty=r_data.get("difficulty", 2),
                    duration_minutes=r_data.get("duration_minutes"),
                    quality_score=r_data.get("quality_score", 0.8),
                    description=r_data.get("description", ""),
                    tags=r_data.get("tags", []),
                    why_recommended=r_data.get("why_recommended", "")
                )
                self._add_resource(resource)

    def _add_resource(self, resource: LearningResource):
        """Add a resource to the index."""
        self.resources[resource.id] = resource
        if resource.concept_id not in self.concept_resources:
            self.concept_resources[resource.concept_id] = []
        if resource.id not in self.concept_resources[resource.concept_id]:
            self.concept_resources[resource.concept_id].append(resource.id)

    # ==================== Resource Retrieval ====================

    def get_resources(
        self,
        concept_id: str,
        difficulty: Optional[int] = None,
        source_type: Optional[str] = None,
        limit: int = 5
    ) -> List[LearningResource]:
        """
        Get curated resources for a concept.

        Args:
            concept_id: The concept to get resources for
            difficulty: Optional filter (1=easy, 2=medium, 3=hard)
            source_type: Optional filter (youtube, article, interactive, practice)
            limit: Maximum number to return

        Returns:
            List of resources sorted by quality score
        """
        resource_ids = self.concept_resources.get(concept_id, [])
        resources = [self.resources[rid] for rid in resource_ids if rid in self.resources]

        # Apply filters
        if difficulty is not None:
            resources = [r for r in resources if r.difficulty == difficulty]

        if source_type is not None:
            resources = [r for r in resources if r.source_type == source_type]

        # Sort by quality
        resources.sort(key=lambda r: r.quality_score, reverse=True)

        return resources[:limit]

    def get_best_resource(
        self,
        concept_id: str,
        preferred_type: str = "youtube"
    ) -> Optional[LearningResource]:
        """Get the single best resource for a concept."""
        resources = self.get_resources(concept_id, source_type=preferred_type, limit=1)
        if resources:
            return resources[0]

        # Fallback to any type
        resources = self.get_resources(concept_id, limit=1)
        return resources[0] if resources else None

    def get_prescription_resources(
        self,
        concept_id: str,
        mastery: float = 0.5
    ) -> Dict[str, List[LearningResource]]:
        """
        Get resources organized by learning phase.

        Returns:
            {
                "understand": [video resources],
                "practice": [interactive resources],
                "verify": []  # Handled by quiz system
            }
        """
        # Determine difficulty based on mastery
        if mastery < 0.3:
            target_difficulty = 1
        elif mastery < 0.6:
            target_difficulty = 2
        else:
            target_difficulty = 3

        # Get understanding resources (videos)
        understand_resources = self.get_resources(
            concept_id,
            source_type="youtube",
            limit=2
        )

        # Get practice resources (interactive)
        practice_resources = self.get_resources(
            concept_id,
            source_type="interactive",
            limit=2
        )

        return {
            "understand": understand_resources,
            "practice": practice_resources,
            "verify": []
        }

    # ==================== Dynamic Search (Tavily) ====================

    async def search_resources(
        self,
        query: str,
        concept_id: str,
        max_results: int = 5
    ) -> List[LearningResource]:
        """
        Search for educational resources using Tavily.

        Falls back to curated resources if Tavily unavailable.
        """
        if not self.tavily_client:
            return self.get_resources(concept_id, limit=max_results)

        try:
            # Search with educational focus
            search_query = f"{query} tutorial explanation linear algebra"
            results = self.tavily_client.search(
                query=search_query,
                search_depth="advanced",
                max_results=max_results * 2,  # Get more to filter
                include_domains=[
                    "youtube.com",
                    "khanacademy.org",
                    "brilliant.org",
                    "mathworld.wolfram.com",
                    "mit.edu",
                ]
            )

            resources = []
            for result in results.get("results", []):
                resource = self._result_to_resource(result, concept_id)
                if resource and resource.quality_score > 0.5:
                    resources.append(resource)

            # Sort by quality and limit
            resources.sort(key=lambda r: r.quality_score, reverse=True)
            return resources[:max_results]

        except Exception as e:
            print(f"Tavily search error: {e}")
            return self.get_resources(concept_id, limit=max_results)

    def _result_to_resource(
        self,
        result: Dict,
        concept_id: str
    ) -> Optional[LearningResource]:
        """Convert a Tavily search result to a LearningResource."""
        url = result.get("url", "")
        title = result.get("title", "")

        # Determine source type
        if "youtube.com" in url or "youtu.be" in url:
            source_type = "youtube"
        elif "khanacademy.org" in url:
            source_type = "interactive"
        else:
            source_type = "article"

        # Calculate quality score
        quality_score = self._calculate_quality(url, title)

        # Extract timestamp if YouTube
        timestamp = self._extract_timestamp(url)

        return LearningResource(
            id=f"search_{hash(url) % 10000}",
            title=title,
            url=url,
            source_type=source_type,
            concept_id=concept_id,
            difficulty=2,  # Default
            quality_score=quality_score,
            description=result.get("content", "")[:200],
            timestamp=timestamp
        )

    def _calculate_quality(self, url: str, title: str) -> float:
        """Calculate quality score based on source and title."""
        quality = 0.6  # Base score

        # Check trusted sources
        for domain, info in TRUSTED_SOURCES.items():
            if domain in url.lower():
                quality = max(quality, info.get("weight", 0.7))

                # Check specific channels for YouTube
                if domain == "youtube.com" and "channels" in info:
                    title_lower = title.lower()
                    for channel, channel_weight in info["channels"].items():
                        if channel in title_lower:
                            quality = max(quality, channel_weight)
                            break
                break

        return quality

    def _extract_timestamp(self, url: str) -> Optional[str]:
        """Extract timestamp from YouTube URL if present."""
        # Match t=XXX or t=XmYs patterns
        patterns = [
            r't=(\d+)',  # t=123 (seconds)
            r't=(\d+)m(\d+)s',  # t=2m34s
            r'(?:&|\?)t=(\d+)',  # &t=123
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                groups = match.groups()
                if len(groups) == 1:
                    seconds = int(groups[0])
                    minutes = seconds // 60
                    secs = seconds % 60
                    return f"{minutes}:{secs:02d}"
                elif len(groups) == 2:
                    return f"{groups[0]}:{int(groups[1]):02d}"

        return None

    # ==================== Formatting ====================

    def format_resources_for_display(self, resources: List[LearningResource]) -> str:
        """Format resources as markdown for display in chat."""
        if not resources:
            return "No resources found for this concept."

        lines = ["**Recommended Resources:**\n"]

        for r in resources:
            emoji = {
                "youtube": "🎥",
                "article": "📄",
                "interactive": "🎮",
                "practice": "✍️"
            }.get(r.source_type, "📌")

            duration = f" ({r.duration_minutes} min)" if r.duration_minutes else ""
            timestamp = f" @ {r.timestamp}" if r.timestamp else ""
            difficulty = ["🟢", "🟡", "🔴"][r.difficulty - 1]

            lines.append(f"{emoji} **[{r.title}]({r.url})**{timestamp}{duration}")
            lines.append(f"   {difficulty} {r.description[:80]}...")

            if r.why_recommended:
                lines.append(f"   *Why: {r.why_recommended}*")
            lines.append("")

        return "\n".join(lines)

    def to_frontend_format(self, resources: List[LearningResource]) -> List[Dict]:
        """Convert resources to structured format for frontend."""
        return [
            {
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "type": r.source_type,
                "difficulty": r.difficulty,
                "duration_minutes": r.duration_minutes,
                "quality_score": r.quality_score,
                "description": r.description,
                "timestamp": r.timestamp,
                "why_recommended": r.why_recommended
            }
            for r in resources
        ]

    # ==================== Statistics ====================

    def get_stats(self) -> dict:
        """Get resource database statistics."""
        by_type = {}
        by_concept = {}

        for r in self.resources.values():
            by_type[r.source_type] = by_type.get(r.source_type, 0) + 1
            by_concept[r.concept_id] = by_concept.get(r.concept_id, 0) + 1

        return {
            "total_resources": len(self.resources),
            "by_type": by_type,
            "by_concept": by_concept,
            "avg_quality": sum(r.quality_score for r in self.resources.values()) / len(self.resources) if self.resources else 0,
            "tavily_available": self.tavily_client is not None
        }
