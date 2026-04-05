#!/usr/bin/env python3
"""
DSPy signatures for email classification.
Defines the input/output structure for LLM-based email categorization.
"""

import dspy
from typing import Literal


class EmailClassification(dspy.Signature):
    """Classify an email into ecommerce, political, or none categories.
    
    This signature defines the structure for email classification:
    - Input: sender email, subject line, and body text
    - Output: category (ecommerce/political/none), reasoning, and confidence score
    
    The signature is used by DSPy modules to automatically generate appropriate
    prompts for different language models.
    """
    
    sender = dspy.InputField(
        desc="Email sender address"
    )
    subject = dspy.InputField(
        desc="Email subject line"
    )
    body = dspy.InputField(
        desc="Email body text (truncated to key content)"
    )
    
    category: Literal['ecommerce', 'political', 'none'] = dspy.OutputField(
        desc="Classification category: 'ecommerce' for marketing/retail emails, "
             "'political' for campaign/donation emails, 'none' for everything else"
    )
    reason: str = dspy.OutputField(
        desc="Brief explanation for the classification decision"
    )
    confidence: float = dspy.OutputField(
        desc="Confidence score between 0.0 and 1.0 indicating certainty of classification"
    )


class EmailClassificationDetailed(dspy.Signature):
    """Extended email classification with additional context fields.
    
    This signature includes more detailed analysis for difficult cases:
    - Includes sender domain analysis
    - Identifies key phrases that influenced the decision
    - Provides alternative classifications if confidence is low
    """
    
    sender = dspy.InputField(desc="Email sender address")
    subject = dspy.InputField(desc="Email subject line")
    body = dspy.InputField(desc="Email body text")
    
    # Analysis fields
    sender_type: str = dspy.OutputField(
        desc="Type of sender: 'retail', 'campaign', 'service', 'personal', or 'organization'"
    )
    key_phrases: str = dspy.OutputField(
        desc="Comma-separated list of key phrases that indicate the category"
    )
    
    # Classification fields
    category: Literal['ecommerce', 'political', 'none'] = dspy.OutputField(
        desc="Primary classification category"
    )
    alternative_category: Literal['ecommerce', 'political', 'none', 'uncertain'] = dspy.OutputField(
        desc="Alternative category if confidence is low"
    )
    reason: str = dspy.OutputField(
        desc="Detailed explanation for the classification"
    )
    confidence: float = dspy.OutputField(
        desc="Confidence score between 0.0 and 1.0"
    )


class ConfidenceCheck(dspy.Signature):
    """Check if an email needs deeper analysis based on ambiguity signals.
    
    Used for two-stage classification to identify emails that require
    more detailed analysis with chain-of-thought reasoning.
    """
    
    sender = dspy.InputField(desc="Email sender address")
    subject = dspy.InputField(desc="Email subject line")
    body_snippet = dspy.InputField(desc="First 500 characters of email body")
    
    needs_deeper_analysis: bool = dspy.OutputField(
        desc="True if email appears ambiguous and needs detailed chain-of-thought analysis"
    )
    ambiguity_reason: str = dspy.OutputField(
        desc="Brief explanation of why email is ambiguous (if applicable)"
    )


class EvaluateFaithfulness(dspy.Signature):
    """Evaluate if classification reasoning is faithful to the email content.
    
    Used as a metric to ensure the LLM's reasoning is grounded in the actual
    email content rather than hallucinations or assumptions.
    """
    
    email_content = dspy.InputField(desc="Full email content (sender, subject, body)")
    classification = dspy.InputField(desc="Predicted category")
    reasoning = dspy.InputField(desc="Reasoning provided for classification")
    
    is_faithful: bool = dspy.OutputField(
        desc="True if reasoning is based on actual email content"
    )
    unsupported_claims: str = dspy.OutputField(
        desc="List of claims in reasoning not supported by email content"
    )


class EmailTriage(dspy.Signature):
    """Triage email for priority, urgency, and flexible categories.
    
    Used for Tier 2 lightweight LLM processing with subject + snippet only.
    Outputs priority (high/medium/low), urgency, relevance, and categories
    for dashboard grouping and filtering.
    """
    
    sender = dspy.InputField(desc="Email sender address")
    subject = dspy.InputField(desc="Email subject line")
    snippet = dspy.InputField(desc="Short snippet or first 300 chars of body")
    
    priority: Literal["high", "medium", "low"] = dspy.OutputField(
        desc="Overall priority: high for receipts/transactions/personal/critical, "
             "low for political/news/marketing, medium otherwise"
    )
    urgency: Literal["high", "medium", "low"] = dspy.OutputField(
        desc="Time sensitivity: high if needs quick action, low if can wait"
    )
    relevance: float = dspy.OutputField(
        desc="Relevance score 0.0 to 1.0 for how likely the user cares about this email"
    )
    categories: str = dspy.OutputField(
        desc="Comma-separated categories: receipts, transactions, personal, critical, "
             "political, news, marketing, ecommerce, other"
    )
    reason: str = dspy.OutputField(
        desc="Brief explanation for the triage decision"
    )


class EmailSummary(dspy.Signature):
    """Generate headline and summary for an email.
    
    Used for Tier 3 full LLM processing on high-priority emails or on demand.
    Produces a short headline and one-sentence summary for dashboard display.
    """
    
    sender = dspy.InputField(desc="Email sender address")
    subject = dspy.InputField(desc="Email subject line")
    body = dspy.InputField(desc="Email body text")
    
    headline: str = dspy.OutputField(
        desc="Short catchy headline (5-10 words) capturing the key point"
    )
    summary: str = dspy.OutputField(
        desc="One-sentence summary of the email content and any action needed"
    )
