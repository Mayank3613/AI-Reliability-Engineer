"""
Layer 9 — Safety
Action Validator: Validates every agent-proposed action against safety rules
before it is surfaced to users or executed automatically.
"""

import yaml
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from enum import Enum

RULES_PATH = Path(__file__).parent / "safety_rules.yaml"


class ValidationResult(str, Enum):
    ALLOWED = "allowed"
    ALLOWED_WITH_CONFIRMATION = "allowed_with_confirmation"
    BLOCKED = "blocked"


@dataclass
class ActionValidationReport:
    action: str
    result: ValidationResult
    reason: str
    requires_human_review: bool
    safety_rule_triggered: Optional[str] = None
    recommended_alternative: Optional[str] = None


class ActionValidator:
    """
    Validates agent actions against the AIRE safety rules YAML.
    Instantiate once and reuse across agent calls.
    """

    def __init__(self, rules_path: Path = RULES_PATH):
        with open(rules_path, "r") as f:
            self.rules = yaml.safe_load(f)

        self.blocked = set(self.rules.get("blocked_actions", []))
        self.confirmation_required = set(self.rules.get("confirmation_required", []))
        self.allowed_read = set(self.rules.get("allowed_read", []))
        self.allowed_write = set(self.rules.get("allowed_write_advisory", []))
        self.min_confidence = self.rules.get("recommendation_rules", {}).get(
            "min_confidence_threshold", 0.70
        )

    def validate_action(self, action: str, context: Optional[dict] = None) -> ActionValidationReport:
        """
        Validate a single action string.

        Args:
            action: The action identifier (snake_case)
            context: Optional metadata about the action (resource, user, etc.)

        Returns:
            ActionValidationReport with full decision + reason
        """
        action_lower = action.lower().strip().replace(" ", "_")

        # 1. Hard block
        if action_lower in self.blocked:
            return ActionValidationReport(
                action=action,
                result=ValidationResult.BLOCKED,
                reason=f"Action '{action}' is in the AIRE blocked list. This action can cause irreversible damage.",
                requires_human_review=False,
                safety_rule_triggered="blocked_actions",
                recommended_alternative="Review the action manually in the AIRE dashboard.",
            )

        # 2. Requires confirmation
        if action_lower in self.confirmation_required:
            return ActionValidationReport(
                action=action,
                result=ValidationResult.ALLOWED_WITH_CONFIRMATION,
                reason=f"Action '{action}' is allowed but requires explicit human confirmation before execution.",
                requires_human_review=True,
                safety_rule_triggered="confirmation_required",
            )

        # 3. Known safe read action
        if action_lower in self.allowed_read:
            return ActionValidationReport(
                action=action,
                result=ValidationResult.ALLOWED,
                reason=f"Action '{action}' is a pre-approved read action.",
                requires_human_review=False,
            )

        # 4. Known safe write action
        if action_lower in self.allowed_write:
            return ActionValidationReport(
                action=action,
                result=ValidationResult.ALLOWED_WITH_CONFIRMATION,
                reason=f"Action '{action}' is a write action — advisory only. Human must approve execution.",
                requires_human_review=True,
            )

        # 5. Unknown action — allow with strong warning
        return ActionValidationReport(
            action=action,
            result=ValidationResult.ALLOWED_WITH_CONFIRMATION,
            reason=f"Action '{action}' is not in the pre-approved list. Treating as unclassified — human review required.",
            requires_human_review=True,
            recommended_alternative="Add this action to safety_rules.yaml after security review.",
        )

    def validate_recommendation(
        self,
        recommendation_text: str,
        confidence: float,
        proposed_actions: list[str],
    ) -> dict:
        """
        Validate a full recommendation before surfacing to the dashboard.
        Checks confidence threshold + all proposed actions.
        """
        issues = []
        blocked_actions = []
        confirmation_actions = []

        # Confidence gate
        if confidence < self.min_confidence:
            issues.append(
                f"Confidence {confidence:.0%} is below minimum threshold {self.min_confidence:.0%}. "
                "This recommendation should not be shown without further validation."
            )

        # Validate each action
        for action in proposed_actions:
            report = self.validate_action(action)
            if report.result == ValidationResult.BLOCKED:
                blocked_actions.append(action)
                issues.append(f"BLOCKED: {action} — {report.reason}")
            elif report.result == ValidationResult.ALLOWED_WITH_CONFIRMATION:
                confirmation_actions.append(action)

        is_safe = len(blocked_actions) == 0 and confidence >= self.min_confidence

        return {
            "is_safe_to_surface": is_safe,
            "confidence": confidence,
            "blocked_actions": blocked_actions,
            "confirmation_required_actions": confirmation_actions,
            "issues": issues,
            "recommendation_preview": recommendation_text[:200] + "..." if len(recommendation_text) > 200 else recommendation_text,
        }


# Singleton
_validator: Optional[ActionValidator] = None


def get_validator() -> ActionValidator:
    global _validator
    if _validator is None:
        _validator = ActionValidator()
    return _validator


def validate(action: str, context: Optional[dict] = None) -> ActionValidationReport:
    """Convenience wrapper for one-off validation."""
    return get_validator().validate_action(action, context)
