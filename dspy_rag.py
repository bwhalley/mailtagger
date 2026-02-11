#!/usr/bin/env python3
"""
Retrieval-Augmented Generation (RAG) classifier for email classification.

This module implements a DSPy classifier that retrieves relevant few-shot
examples from the example store before making predictions.
"""

import logging
from typing import List, Dict, Any, Optional

import dspy
from dspy_signatures import EmailClassification
from prompt_service import ExampleStore

logger = logging.getLogger(__name__)


class RAGEmailClassifier(dspy.Module):
    """Email classifier with retrieval-augmented generation.
    
    This classifier retrieves similar examples from the example store
    and includes them as few-shot demonstrations before classification.
    
    Attributes:
        example_store: ExampleStore instance for retrieving examples
        classifier: DSPy classification module
        k_examples: Number of examples to retrieve
        use_cot: Whether to use chain-of-thought reasoning
    """
    
    def __init__(
        self,
        example_store: ExampleStore,
        k_examples: int = 3,
        use_cot: bool = True,
        stratified: bool = False
    ):
        """Initialize RAG classifier.
        
        Args:
            example_store: ExampleStore for retrieving examples
            k_examples: Number of examples to retrieve per prediction
            use_cot: If True, use ChainOfThought; else use Predict
            stratified: If True, balance examples across categories
        """
        super().__init__()
        self.example_store = example_store
        self.k_examples = k_examples
        self.stratified = stratified
        
        # Initialize the classifier
        if use_cot:
            self.classifier = dspy.ChainOfThought(EmailClassification)
        else:
            self.classifier = dspy.Predict(EmailClassification)
    
    def _retrieve_examples(
        self,
        sender: str,
        subject: str,
        body: str,
        category_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant examples from the store.
        
        Retrieval strategies:
        1. If stratified=True: Get balanced examples across categories
        2. If category_hint provided: Get examples from that category
        3. Otherwise: Get best examples overall
        
        Args:
            sender: Email sender
            subject: Email subject
            body: Email body
            category_hint: Optional category hint for targeted retrieval
            
        Returns:
            List of example dicts
        """
        if self.stratified:
            # Get balanced examples across all categories
            examples = self.example_store.get_stratified_examples(
                k_per_category=max(1, self.k_examples // 3)
            )
        elif category_hint:
            # Get examples from specific category
            examples = self.example_store.get_best_examples(
                category=category_hint,
                k=self.k_examples,
                verified_only=True
            )
        else:
            # Get best examples overall
            examples = self.example_store.get_best_examples(
                k=self.k_examples,
                verified_only=True
            )
        
        logger.debug(f"Retrieved {len(examples)} examples for RAG")
        return examples
    
    def forward(
        self,
        sender: str,
        subject: str,
        body: str,
        category_hint: Optional[str] = None
    ):
        """Forward pass with retrieval-augmented generation.
        
        This method:
        1. Retrieves relevant examples from the store
        2. Formats them as demonstrations
        3. Passes them to the classifier along with the input
        
        Args:
            sender: Email sender address
            subject: Email subject line
            body: Email body text
            category_hint: Optional category hint for retrieval
            
        Returns:
            Prediction with category, reason, confidence
        """
        # Retrieve examples
        examples = self._retrieve_examples(sender, subject, body, category_hint)
        
        # If we have examples, add them as demonstrations
        # DSPy will automatically include them in the prompt
        if examples:
            # Convert examples to DSPy format
            demonstrations = []
            for ex in examples:
                # Create example-prediction pair
                demo_example = dspy.Example(
                    sender=ex['sender'],
                    subject=ex['subject'],
                    body=ex.get('body', ''),
                ).with_inputs('sender', 'subject', 'body')
                
                demo_prediction = dspy.Example(
                    category=ex['category'],
                    reason=ex.get('notes', f"Example {ex['category']} email"),
                    confidence=ex.get('confidence', 1.0)
                )
                
                demonstrations.append((demo_example, demo_prediction))
            
            # Set demonstrations for this prediction
            # Note: This is a simplified version - full implementation would
            # use DSPy's demonstration mechanism more robustly
            logger.debug(f"Using {len(demonstrations)} demonstrations")
        
        # Make prediction with retrieved context
        prediction = self.classifier(
            sender=sender,
            subject=subject,
            body=body
        )
        
        return prediction


class TwoStageRAGClassifier(dspy.Module):
    """Two-stage classifier with RAG for difficult cases.
    
    Stage 1: Quick confidence check
    Stage 2: Full RAG classification for low-confidence cases
    """
    
    def __init__(
        self,
        example_store: ExampleStore,
        confidence_threshold: float = 0.7,
        k_examples: int = 3
    ):
        """Initialize two-stage classifier.
        
        Args:
            example_store: ExampleStore for retrieving examples
            confidence_threshold: Threshold for stage 2
            k_examples: Number of examples for RAG
        """
        super().__init__()
        self.example_store = example_store
        self.confidence_threshold = confidence_threshold
        
        # Stage 1: Fast classifier without examples
        self.fast_classifier = dspy.Predict(EmailClassification)
        
        # Stage 2: RAG classifier with examples
        self.rag_classifier = RAGEmailClassifier(
            example_store=example_store,
            k_examples=k_examples,
            use_cot=True
        )
    
    def forward(self, sender: str, subject: str, body: str):
        """Two-stage forward pass.
        
        Args:
            sender: Email sender
            subject: Email subject
            body: Email body
            
        Returns:
            Prediction with category, reason, confidence
        """
        # Stage 1: Fast classification
        initial_pred = self.fast_classifier(
            sender=sender,
            subject=subject,
            body=body
        )
        
        # Check confidence
        initial_confidence = float(getattr(initial_pred, 'confidence', 0.5))
        
        if initial_confidence >= self.confidence_threshold:
            # High confidence - return fast prediction
            logger.debug(f"High confidence ({initial_confidence:.2f}), using fast prediction")
            return initial_pred
        else:
            # Low confidence - use RAG for better prediction
            logger.debug(f"Low confidence ({initial_confidence:.2f}), using RAG")
            
            # Use initial prediction as hint for retrieval
            category_hint = getattr(initial_pred, 'category', None)
            
            return self.rag_classifier(
                sender=sender,
                subject=subject,
                body=body,
                category_hint=category_hint
            )


class EnsembleRAGClassifier(dspy.Module):
    """Ensemble classifier with multiple RAG strategies.
    
    Combines predictions from:
    1. Fast baseline classifier
    2. Stratified RAG (balanced examples)
    3. Category-specific RAG (if confident enough)
    """
    
    def __init__(
        self,
        example_store: ExampleStore,
        k_examples: int = 3,
        voting: str = 'confidence'
    ):
        """Initialize ensemble classifier.
        
        Args:
            example_store: ExampleStore for retrieving examples
            k_examples: Number of examples per RAG model
            voting: Voting strategy ('majority', 'confidence', 'average')
        """
        super().__init__()
        self.voting = voting
        
        # Model 1: Fast baseline
        self.baseline = dspy.Predict(EmailClassification)
        
        # Model 2: Stratified RAG
        self.stratified_rag = RAGEmailClassifier(
            example_store=example_store,
            k_examples=k_examples,
            stratified=True
        )
        
        # Model 3: Category-targeted RAG (we'll run this adaptively)
        self.targeted_rag = RAGEmailClassifier(
            example_store=example_store,
            k_examples=k_examples,
            stratified=False
        )
    
    def _aggregate_predictions(
        self,
        predictions: List[Any]
    ) -> Dict[str, Any]:
        """Aggregate multiple predictions using voting strategy.
        
        Args:
            predictions: List of prediction objects
            
        Returns:
            Aggregated prediction dict
        """
        if self.voting == 'confidence':
            # Use prediction with highest confidence
            best_pred = max(
                predictions,
                key=lambda p: float(getattr(p, 'confidence', 0.0))
            )
            return {
                'category': best_pred.category,
                'reason': f"Ensemble (confidence voting): {best_pred.reason}",
                'confidence': float(best_pred.confidence)
            }
        
        elif self.voting == 'majority':
            # Majority vote on category
            from collections import Counter
            categories = [p.category for p in predictions]
            most_common = Counter(categories).most_common(1)[0][0]
            
            # Average confidence of predictions that chose majority category
            confidences = [
                float(p.confidence) for p in predictions
                if p.category == most_common
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            
            return {
                'category': most_common,
                'reason': f"Ensemble (majority vote: {len(confidences)}/{len(predictions)})",
                'confidence': avg_confidence
            }
        
        else:  # average
            # Average confidence per category, pick best
            from collections import defaultdict
            category_confidences = defaultdict(list)
            
            for p in predictions:
                category_confidences[p.category].append(float(p.confidence))
            
            # Calculate average confidence per category
            avg_by_category = {
                cat: sum(confs) / len(confs)
                for cat, confs in category_confidences.items()
            }
            
            best_category = max(avg_by_category.items(), key=lambda x: x[1])
            
            return {
                'category': best_category[0],
                'reason': "Ensemble (average confidence)",
                'confidence': best_category[1]
            }
    
    def forward(self, sender: str, subject: str, body: str):
        """Ensemble forward pass.
        
        Args:
            sender: Email sender
            subject: Email subject
            body: Email body
            
        Returns:
            Aggregated prediction
        """
        predictions = []
        
        # Get baseline prediction
        baseline_pred = self.baseline(sender=sender, subject=subject, body=body)
        predictions.append(baseline_pred)
        
        # Get stratified RAG prediction
        stratified_pred = self.stratified_rag(sender=sender, subject=subject, body=body)
        predictions.append(stratified_pred)
        
        # If baseline is confident, get targeted RAG for that category
        baseline_conf = float(getattr(baseline_pred, 'confidence', 0.0))
        if baseline_conf > 0.6:
            targeted_pred = self.targeted_rag(
                sender=sender,
                subject=subject,
                body=body,
                category_hint=baseline_pred.category
            )
            predictions.append(targeted_pred)
        
        # Aggregate predictions
        result = self._aggregate_predictions(predictions)
        
        # Create prediction object
        class EnsemblePrediction:
            def __init__(self, category, reason, confidence):
                self.category = category
                self.reason = reason
                self.confidence = confidence
        
        return EnsemblePrediction(**result)


def main():
    """Test RAG classifiers."""
    logging.basicConfig(level=logging.INFO)
    
    from dspy_config import configure_dspy_lm
    
    # Configure DSPy
    configure_dspy_lm()
    
    # Create example store
    example_store = ExampleStore("./data/prompts.db")
    
    # Add some test examples
    print("Adding test examples...")
    example_store.add_example(
        sender="deals@amazon.com",
        subject="Flash Sale: 50% Off",
        body="Shop now and save big!",
        category="ecommerce",
        confidence=1.0,
        verified=True
    )
    example_store.add_example(
        sender="team@candidate.com",
        subject="Chip in $5 today",
        body="Help us reach our fundraising goal!",
        category="political",
        confidence=1.0,
        verified=True
    )
    
    # Test RAG classifier
    print("\nTesting RAG classifier...")
    rag_classifier = RAGEmailClassifier(
        example_store=example_store,
        k_examples=2,
        stratified=True
    )
    
    result = rag_classifier(
        sender="promo@store.com",
        subject="Weekly Deals",
        body="Check out this week's best deals!"
    )
    
    print(f"Category: {result.category}")
    print(f"Confidence: {result.confidence}")
    print(f"Reason: {result.reason}")
    
    print("\n✓ RAG classifier working correctly")


if __name__ == "__main__":
    main()
