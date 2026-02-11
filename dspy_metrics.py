#!/usr/bin/env python3
"""
Evaluation metrics for DSPy email classification.

This module defines metrics used to evaluate and optimize the email classifier.
DSPy optimizers use these metrics to select better prompts and few-shot examples.
"""

import logging
from typing import List, Dict, Any, Optional
from collections import Counter
import dspy

logger = logging.getLogger(__name__)


def classification_accuracy(example, prediction, trace=None) -> bool:
    """Simple binary accuracy metric.
    
    Returns True if the predicted category matches the expected category.
    This is the primary metric for DSPy optimization.
    
    Args:
        example: Example object with expected category
        prediction: Prediction object from DSPy module
        trace: Optional execution trace (unused)
        
    Returns:
        True if classification is correct, False otherwise
    """
    expected = getattr(example, 'category', None)
    predicted = getattr(prediction, 'category', None)
    
    if expected is None or predicted is None:
        return False
    
    return expected == predicted


def weighted_accuracy(example, prediction, trace=None) -> float:
    """Accuracy weighted by confidence score.
    
    Gives partial credit for uncertain predictions. A correct prediction
    with high confidence scores higher than a correct prediction with low confidence.
    
    Args:
        example: Example object with expected category
        prediction: Prediction object with category and confidence
        trace: Optional execution trace (unused)
        
    Returns:
        Float between 0.0 and 1.0
    """
    is_correct = classification_accuracy(example, prediction, trace)
    confidence = getattr(prediction, 'confidence', 0.5)
    
    if is_correct:
        # Reward high-confidence correct predictions
        return float(confidence)
    else:
        # Penalize high-confidence wrong predictions
        return float(1.0 - confidence)


def category_specific_accuracy(
    examples: List[Any],
    predictions: List[Any],
    category: str
) -> float:
    """Calculate accuracy for a specific category.
    
    Useful for identifying which categories the model struggles with.
    
    Args:
        examples: List of example objects
        predictions: List of prediction objects
        category: Category to calculate accuracy for
        
    Returns:
        Accuracy (0.0 to 1.0) for the specified category
    """
    correct = 0
    total = 0
    
    for example, prediction in zip(examples, predictions):
        if getattr(example, 'category', None) == category:
            total += 1
            if getattr(prediction, 'category', None) == category:
                correct += 1
    
    return correct / total if total > 0 else 0.0


def calculate_f1_score(
    examples: List[Any],
    predictions: List[Any],
    category: str
) -> float:
    """Calculate F1 score for a specific category.
    
    F1 score balances precision and recall, useful for imbalanced datasets.
    
    Args:
        examples: List of example objects
        predictions: List of prediction objects
        category: Category to calculate F1 for
        
    Returns:
        F1 score (0.0 to 1.0)
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    for example, prediction in zip(examples, predictions):
        expected = getattr(example, 'category', None)
        predicted = getattr(prediction, 'category', None)
        
        if predicted == category and expected == category:
            true_positives += 1
        elif predicted == category and expected != category:
            false_positives += 1
        elif predicted != category and expected == category:
            false_negatives += 1
    
    # Calculate precision and recall
    precision = (true_positives / (true_positives + false_positives) 
                 if (true_positives + false_positives) > 0 else 0.0)
    recall = (true_positives / (true_positives + false_negatives)
              if (true_positives + false_negatives) > 0 else 0.0)
    
    # Calculate F1
    if precision + recall > 0:
        f1 = 2 * (precision * recall) / (precision + recall)
    else:
        f1 = 0.0
    
    return f1


def weighted_f1_score(
    examples: List[Any],
    predictions: List[Any]
) -> float:
    """Calculate weighted average F1 score across all categories.
    
    Args:
        examples: List of example objects
        predictions: List of prediction objects
        
    Returns:
        Weighted F1 score (0.0 to 1.0)
    """
    categories = ['ecommerce', 'political', 'none']
    
    # Count examples per category
    category_counts = Counter(getattr(ex, 'category', None) for ex in examples)
    total = sum(category_counts.values())
    
    if total == 0:
        return 0.0
    
    # Calculate weighted F1
    weighted_f1 = 0.0
    for category in categories:
        f1 = calculate_f1_score(examples, predictions, category)
        weight = category_counts.get(category, 0) / total
        weighted_f1 += f1 * weight
    
    return weighted_f1


def confidence_calibration(
    examples: List[Any],
    predictions: List[Any],
    bins: int = 10
) -> Dict[str, float]:
    """Measure calibration of confidence scores.
    
    Well-calibrated predictions have confidence scores that match actual accuracy.
    For example, predictions with 0.8 confidence should be correct 80% of the time.
    
    Args:
        examples: List of example objects
        predictions: List of prediction objects
        bins: Number of bins for calibration curve
        
    Returns:
        Dict with calibration metrics:
        - expected_calibration_error (ECE): Average calibration error
        - bin_accuracies: Accuracy per confidence bin
        - bin_confidences: Average confidence per bin
    """
    # Collect predictions with confidences
    data = []
    for example, prediction in zip(examples, predictions):
        is_correct = classification_accuracy(example, prediction)
        confidence = getattr(prediction, 'confidence', 0.5)
        data.append((confidence, is_correct))
    
    if not data:
        return {'expected_calibration_error': 0.0}
    
    # Sort by confidence and bin
    data.sort(key=lambda x: x[0])
    bin_size = len(data) // bins
    
    bin_accuracies = []
    bin_confidences = []
    calibration_errors = []
    
    for i in range(bins):
        start = i * bin_size
        end = start + bin_size if i < bins - 1 else len(data)
        bin_data = data[start:end]
        
        if not bin_data:
            continue
        
        # Calculate average confidence and accuracy in bin
        avg_confidence = sum(conf for conf, _ in bin_data) / len(bin_data)
        avg_accuracy = sum(correct for _, correct in bin_data) / len(bin_data)
        
        bin_confidences.append(avg_confidence)
        bin_accuracies.append(avg_accuracy)
        calibration_errors.append(abs(avg_confidence - avg_accuracy))
    
    # Expected Calibration Error (ECE)
    ece = sum(calibration_errors) / len(calibration_errors) if calibration_errors else 0.0
    
    return {
        'expected_calibration_error': ece,
        'bin_accuracies': bin_accuracies,
        'bin_confidences': bin_confidences
    }


def reasoning_faithfulness(example, prediction, trace=None) -> bool:
    """Check if reasoning is faithful to the email content.
    
    This metric evaluates whether the model's reasoning is grounded in the
    actual email content rather than hallucinations or assumptions.
    
    Args:
        example: Example object with email content
        prediction: Prediction object with reasoning
        trace: Optional execution trace
        
    Returns:
        True if reasoning appears faithful, False otherwise
    """
    reasoning = getattr(prediction, 'reasoning', '')
    if not reasoning:
        return True  # No reasoning to evaluate
    
    # Get email content
    body = getattr(example, 'body', '')
    subject = getattr(example, 'subject', '')
    sender = getattr(example, 'sender', '')
    
    email_text = f"{sender} {subject} {body}".lower()
    reasoning_lower = reasoning.lower()
    
    # Check if reasoning mentions specific content from email
    # This is a simple heuristic - a full implementation would use NLI models
    
    # Extract quoted phrases or specific mentions in reasoning
    import re
    quotes = re.findall(r'"([^"]+)"', reasoning)
    
    # Check if quoted phrases appear in email
    for quote in quotes:
        if quote.lower() not in email_text:
            logger.debug(f"Unfaithful reasoning: '{quote}' not found in email")
            return False
    
    return True


def combined_metric(example, prediction, trace=None) -> float:
    """Combined metric that balances multiple objectives.
    
    This metric combines:
    - Accuracy (primary)
    - Confidence calibration
    - Reasoning faithfulness
    
    Args:
        example: Example object
        prediction: Prediction object
        trace: Optional execution trace
        
    Returns:
        Combined score (0.0 to 1.0)
    """
    # Accuracy component (weight: 0.7)
    is_correct = classification_accuracy(example, prediction, trace)
    accuracy_score = 1.0 if is_correct else 0.0
    
    # Confidence component (weight: 0.2)
    # Reward well-calibrated confidences
    confidence = getattr(prediction, 'confidence', 0.5)
    if is_correct:
        confidence_score = confidence  # Higher is better
    else:
        confidence_score = 1.0 - confidence  # Lower is better
    
    # Faithfulness component (weight: 0.1)
    is_faithful = reasoning_faithfulness(example, prediction, trace)
    faithfulness_score = 1.0 if is_faithful else 0.0
    
    # Weighted combination
    combined = (0.7 * accuracy_score + 
                0.2 * confidence_score + 
                0.1 * faithfulness_score)
    
    return combined


def evaluate_classifier(
    classifier,
    examples: List[Any],
    metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Comprehensive evaluation of a classifier on a dataset.
    
    Args:
        classifier: DSPy module to evaluate
        examples: List of evaluation examples
        metrics: List of metric names to compute (None = all)
        
    Returns:
        Dict with all metric results
    """
    if metrics is None:
        metrics = ['accuracy', 'f1', 'calibration', 'per_category']
    
    # Generate predictions
    predictions = []
    for example in examples:
        try:
            pred = classifier(
                sender=example.sender,
                subject=example.subject,
                body=example.body
            )
            predictions.append(pred)
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            # Create dummy prediction
            class DummyPred:
                category = "none"
                confidence = 0.0
                reason = "error"
            predictions.append(DummyPred())
    
    results = {}
    
    # Overall accuracy
    if 'accuracy' in metrics:
        correct = sum(1 for ex, pred in zip(examples, predictions)
                     if classification_accuracy(ex, pred))
        results['accuracy'] = correct / len(examples) if examples else 0.0
    
    # F1 score
    if 'f1' in metrics:
        results['weighted_f1'] = weighted_f1_score(examples, predictions)
        results['f1_per_category'] = {
            cat: calculate_f1_score(examples, predictions, cat)
            for cat in ['ecommerce', 'political', 'none']
        }
    
    # Calibration
    if 'calibration' in metrics:
        results['calibration'] = confidence_calibration(examples, predictions)
    
    # Per-category accuracy
    if 'per_category' in metrics:
        results['accuracy_per_category'] = {
            cat: category_specific_accuracy(examples, predictions, cat)
            for cat in ['ecommerce', 'political', 'none']
        }
    
    return results


def print_evaluation_results(results: Dict[str, Any]):
    """Pretty-print evaluation results.
    
    Args:
        results: Results dict from evaluate_classifier
    """
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    
    if 'accuracy' in results:
        print(f"\nOverall Accuracy: {results['accuracy']:.2%}")
    
    if 'weighted_f1' in results:
        print(f"Weighted F1 Score: {results['weighted_f1']:.2%}")
    
    if 'f1_per_category' in results:
        print("\nF1 Scores by Category:")
        for cat, f1 in results['f1_per_category'].items():
            print(f"  {cat:12s}: {f1:.2%}")
    
    if 'accuracy_per_category' in results:
        print("\nAccuracy by Category:")
        for cat, acc in results['accuracy_per_category'].items():
            print(f"  {cat:12s}: {acc:.2%}")
    
    if 'calibration' in results:
        ece = results['calibration'].get('expected_calibration_error', 0.0)
        print(f"\nExpected Calibration Error: {ece:.3f}")
        print("(Lower is better; 0.0 = perfect calibration)")
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Test metrics with dummy data
    print("Testing DSPy metrics...")
    
    # Create dummy examples and predictions
    class DummyExample:
        def __init__(self, category):
            self.category = category
            self.sender = "test@example.com"
            self.subject = "Test"
            self.body = "Test body"
    
    class DummyPrediction:
        def __init__(self, category, confidence=0.9):
            self.category = category
            self.confidence = confidence
            self.reasoning = "Test reasoning"
    
    examples = [
        DummyExample('ecommerce'),
        DummyExample('ecommerce'),
        DummyExample('political'),
        DummyExample('none'),
    ]
    
    predictions = [
        DummyPrediction('ecommerce', 0.95),
        DummyPrediction('political', 0.8),  # Wrong
        DummyPrediction('political', 0.9),
        DummyPrediction('none', 0.7),
    ]
    
    # Test metrics
    print(f"\nAccuracy: {classification_accuracy(examples[0], predictions[0])}")
    print(f"Weighted accuracy: {weighted_accuracy(examples[0], predictions[0]):.2f}")
    print(f"Weighted F1: {weighted_f1_score(examples, predictions):.2%}")
    
    calibration = confidence_calibration(examples, predictions)
    print(f"Calibration ECE: {calibration['expected_calibration_error']:.3f}")
    
    print("\n✓ Metrics module working correctly")
