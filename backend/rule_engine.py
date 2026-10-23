import re
from typing import List, Dict, Any, Optional
from backend.models import BrandRule, ApprovedClaim

class DeterministicFinding:
    def __init__(
        self,
        rule_id: Optional[str],
        category: str,
        severity: str,
        matched_text: str,
        start_offset: int,
        end_offset: int,
        explanation: str,
        source_reference: Optional[str] = None,
        suggested_correction: Optional[str] = None,
        confidence: float = 1.0,
        requires_human_review: bool = False,
        finding_source: str = "deterministic"
    ):
        self.rule_id = rule_id
        self.category = category
        self.severity = severity
        self.matched_text = matched_text
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.explanation = explanation
        self.source_reference = source_reference
        self.suggested_correction = suggested_correction
        self.confidence = confidence
        self.requires_human_review = requires_human_review
        self.finding_source = finding_source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "matched_text": self.matched_text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "explanation": self.explanation,
            "source_reference": self.source_reference,
            "suggested_correction": self.suggested_correction,
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
            "finding_source": self.finding_source,
        }

class ComplianceRuleEngine:
    def __init__(self, rules: List[BrandRule], approved_claims: List[ApprovedClaim]):
        self.rules = [r for r in rules if r.is_active]
        self.approved_claims = [c for c in approved_claims if c.is_active]

    def analyze(self, text: str) -> List[DeterministicFinding]:
        if not text or not text.strip():
            return []

        raw_findings: List[DeterministicFinding] = []

        # 1. Evaluate configured brand rules
        for rule in self.rules:
            findings = self._evaluate_rule(rule, text)
            raw_findings.extend(findings)

        # 2. Evaluate Claims against Approved Claims Knowledge
        claim_findings = self._evaluate_unverified_claims(text)
        raw_findings.extend(claim_findings)

        # 3. Style & Tone heuristics
        style_findings = self._evaluate_general_style(text)
        raw_findings.extend(style_findings)

        # 4. Deduplicate and sort findings
        deduped = self._deduplicate_findings(raw_findings)
        return deduped

    def _evaluate_rule(self, rule: BrandRule, text: str) -> List[DeterministicFinding]:
        results: List[DeterministicFinding] = []
        category = rule.category
        pattern_str = rule.match_pattern or rule.rule_text

        if not pattern_str:
            return results

        if category in ("prohibited_term", "restricted_claim"):
            # Check for prohibited phrase or term (handling your/their/our variations smoothly)
            raw_pat = pattern_str.strip()
            # If pattern contains 'your', create regex matching 'your|their|our'
            if re.search(r'\byour\b', raw_pat, re.IGNORECASE):
                sub_pat = re.sub(r'\byour\b', r'(?:your|their|our)', re.escape(raw_pat), flags=re.IGNORECASE)
                regex = re.compile(rf"\b{sub_pat}\b", re.IGNORECASE)
            else:
                escaped_pattern = re.escape(raw_pat)
                regex = re.compile(rf"\b{escaped_pattern}\b", re.IGNORECASE)

            for match in regex.finditer(text):
                matched_span = match.group(0)
                results.append(
                    DeterministicFinding(
                        rule_id=rule.id,
                        category=category,
                        severity=rule.severity,
                        matched_text=matched_span,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        explanation=f"{'Restricted claim' if category == 'restricted_claim' else 'Prohibited wording'} detected: '{matched_span}'. {rule.description}",
                        source_reference=rule.source_reference or f"Rule: {rule.name}",
                        suggested_correction=rule.suggested_replacement,
                        confidence=1.0,
                        requires_human_review=(category == "restricted_claim")
                    )
                )

        elif category == "preferred_term":
            # Identify non-preferred phrasing where a preferred term should be used
            # pattern_str is the discouraged term, rule.suggested_replacement is the preferred term
            escaped_pattern = re.escape(pattern_str.strip())
            regex = re.compile(rf"\b{escaped_pattern}\b", re.IGNORECASE)
            for match in regex.finditer(text):
                matched_span = match.group(0)
                preferred = rule.suggested_replacement or "preferred term"
                results.append(
                    DeterministicFinding(
                        rule_id=rule.id,
                        category="preferred_term",
                        severity=rule.severity,
                        matched_text=matched_span,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        explanation=f"Brand terminology violation: '{matched_span}' should be replaced with '{preferred}'. {rule.description}",
                        source_reference=rule.source_reference or f"Rule: {rule.name}",
                        suggested_correction=preferred,
                        confidence=0.95,
                        requires_human_review=False
                    )
                )

        elif category == "required_phrase":
            # Check if mandatory phrase/disclosure is present in the text
            required_phrase = pattern_str.strip()
            # Case-insensitive check
            if required_phrase.lower() not in text.lower():
                results.append(
                    DeterministicFinding(
                        rule_id=rule.id,
                        category="required_phrase",
                        severity=rule.severity,
                        matched_text="(Missing required disclosure)",
                        start_offset=len(text),
                        end_offset=len(text),
                        explanation=f"Mandatory disclosure missing: '{required_phrase}'. {rule.description}",
                        source_reference=rule.source_reference or f"Rule: {rule.name}",
                        suggested_correction=f"\n\n{required_phrase}",
                        confidence=1.0,
                        requires_human_review=False
                    )
                )

        elif category == "tone_voice":
            # Check for specific tone match pattern if provided
            if rule.match_pattern:
                try:
                    escaped = re.escape(rule.match_pattern.strip())
                    regex = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
                    for match in regex.finditer(text):
                        results.append(
                            DeterministicFinding(
                                rule_id=rule.id,
                                category="tone_voice",
                                severity=rule.severity,
                                matched_text=match.group(0),
                                start_offset=match.start(),
                                end_offset=match.end(),
                                explanation=f"Tone guideline triggered: {rule.description}",
                                source_reference=rule.source_reference or f"Rule: {rule.name}",
                                suggested_correction=rule.suggested_replacement,
                                confidence=0.90,
                                requires_human_review=True
                            )
                        )
                except Exception:
                    pass

        return results

    def _evaluate_unverified_claims(self, text: str) -> List[DeterministicFinding]:
        results: List[DeterministicFinding] = []
        # Detect bold unverified quantitative or performance claims
        # e.g., patterns like "double your performance", "10x speed", "100% risk free", "fastest on the market"
        claim_patterns = [
            (r"\b(double(?:s|d)?\s+(?:your|their|our)?\s*performance(?:\s+in\s+[a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)?)?)\b", "Performance multiplier claim"),
            (r"\b(10x\s+(?:faster|growth|productivity|speed))\b", "10x growth/speed claim"),
            (r"\b(guarantees?\s+results(?:\s+for\s+\w+)?)\b", "Unconditional outcome guarantee"),
            (r"\b(100%\s+risk-?free)\b", "Absolute zero-risk claim"),
            (r"\b(#1\s+in\s+the\s+industry|best\s+platform\s+in\s+the\s+world)\b", "Superlative market claim"),
        ]

        approved_statements_lower = [c.claim_statement.lower() for c in self.approved_claims]

        for pattern, claim_type in claim_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matched = match.group(0)
                # Check if this exact claim is corroborated in approved claims
                is_substantiated = any(matched.lower() in app or app in matched.lower() for app in approved_statements_lower)

                if not is_substantiated:
                    results.append(
                        DeterministicFinding(
                            rule_id=None,
                            category="unverified_claim",
                            severity="high",
                            matched_text=matched,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            explanation=f"Unverified claim detected ({claim_type}): '{matched}' has no matching validated evidence in the approved brand claims repository.",
                            source_reference="AUDITRA Fact & Claim Governance Registry",
                            suggested_correction=None,
                            confidence=0.85,
                            requires_human_review=True,
                            finding_source="deterministic"
                        )
                    )

        return results

    def _evaluate_general_style(self, text: str) -> List[DeterministicFinding]:
        results: List[DeterministicFinding] = []

        # Multiple exclamation marks e.g. "!!!"
        for match in re.finditer(r"!{2,}", text):
            results.append(
                DeterministicFinding(
                    rule_id=None,
                    category="formatting_style",
                    severity="low",
                    matched_text=match.group(0),
                    start_offset=match.start(),
                    end_offset=match.end(),
                    explanation="Excessive punctuation: Multiple exclamation points degrade enterprise brand authority.",
                    source_reference="Editorial Style Standard",
                    suggested_correction=".",
                    confidence=1.0,
                    requires_human_review=False
                )
            )

        # ALL-CAPS words with 4+ letters (excluding common acronyms like AI, API, CEO, AUDITRA, SaaS)
        whitelist = {"AUDITRA", "SAAS", "API", "REST", "JSON", "HTTP", "HTTPS", "HTML", "CSS", "UI", "UX", "CEO", "CTO", "CIO", "AI", "ML", "LLM"}
        for match in re.finditer(r"\b[A-Z]{4,}\b", text):
            word = match.group(0)
            if word not in whitelist:
                results.append(
                    DeterministicFinding(
                        rule_id=None,
                        category="formatting_style",
                        severity="low",
                        matched_text=word,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        explanation=f"All-caps text '{word}' may appear aggressive or informal in professional brand communications.",
                        source_reference="Editorial Style Standard",
                        suggested_correction=word.capitalize(),
                        confidence=0.8,
                        requires_human_review=False
                    )
                )

        return results

    def _deduplicate_findings(self, findings: List[DeterministicFinding]) -> List[DeterministicFinding]:
        if not findings:
            return []

        # Priority map for severity
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        # Sort by start_offset, then by higher severity, then longer matched span
        findings.sort(
            key=lambda f: (
                f.start_offset,
                -severity_rank.get(f.severity.lower(), 0),
                -(f.end_offset - f.start_offset)
            )
        )

        deduped: List[DeterministicFinding] = []
        for current in findings:
            # Check overlap with existing accepted findings
            overlap = False
            for accepted in deduped:
                # If exact same offset and matched text
                if accepted.start_offset == current.start_offset and accepted.end_offset == current.end_offset:
                    overlap = True
                    break
                # If nested within same non-zero span and same category
                if current.start_offset > 0 and accepted.start_offset <= current.start_offset < accepted.end_offset:
                    if accepted.category == current.category:
                        overlap = True
                        break

            if not overlap:
                deduped.append(current)

        return deduped
