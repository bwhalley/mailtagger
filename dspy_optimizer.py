#!/usr/bin/env python3
"""
DSPy optimizer for email classification.

This module provides tools to optimize the email classifier using DSPy's
automatic prompt optimization techniques.
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

import dspy
from dspy.teleprompt import BootstrapFewShot, BootstrapFewShotWithRandomSearch, MIPRO

from dspy_signatures import EmailClassification
from dspy_config import configure_dspy_lm, is_configured
from dspy_metrics import (
    classification_accuracy,
    weighted_accuracy,
    combined_metric,
    evaluate_classifier,
    print_evaluation_results
)

logger = logging.getLogger(__name__)


class EmailClassifierModule(dspy.Module):
    """Wrapper module for email classification.
    
    This wraps the signature in a Module so DSPy optimizers can work with it.
    """
    
    def __init__(self, use_cot: bool = True):
        """Initialize classifier module.
        
        Args:
            use_cot: If True, use ChainOfThought; else use basic Predict
        """
        super().__init__()
        if use_cot:
            self.classifier = dspy.ChainOfThought(EmailClassification)
        else:
            self.classifier = dspy.Predict(EmailClassification)
    
    def forward(self, sender: str, subject: str, body: str):
        """Forward pass for classification.
        
        Args:
            sender: Email sender address
            subject: Email subject line
            body: Email body text
            
        Returns:
            Prediction with category, reason, confidence
        """
        return self.classifier(sender=sender, subject=subject, body=body)


def optimize_with_bootstrap_fewshot(
    train_examples: List[Any],
    val_examples: List[Any],
    metric: Callable = classification_accuracy,
    max_bootstrapped_demos: int = 5,
    max_labeled_demos: int = 8,
    max_rounds: int = 1,
    use_cot: bool = True
) -> dspy.Module:
    """Optimize classifier using BootstrapFewShot.
    
    BootstrapFewShot automatically selects good few-shot examples from the
    training set and optimizes their ordering and presentation.
    
    Args:
        train_examples: Training examples (small set, typically 10-50)
        val_examples: Validation examples (larger set for stable metrics)
        metric: Evaluation metric function
        max_bootstrapped_demos: Max examples to include in prompts
        max_labeled_demos: Max examples to consider for selection
        max_rounds: Number of bootstrap rounds
        use_cot: If True, use ChainOfThought reasoning
        
    Returns:
        Optimized classifier module
    """
    logger.info("Starting BootstrapFewShot optimization...")
    logger.info(f"  Train examples: {len(train_examples)}")
    logger.info(f"  Val examples: {len(val_examples)}")
    logger.info(f"  Max demos: {max_bootstrapped_demos}")
    
    # Ensure DSPy is configured
    if not is_configured():
        logger.info("Configuring DSPy LM...")
        configure_dspy_lm()
    
    # Create base classifier
    base_classifier = EmailClassifierModule(use_cot=use_cot)
    
    # Create optimizer
    optimizer = BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
        max_rounds=max_rounds
    )
    
    # Run optimization
    start_time = time.time()
    optimized_classifier = optimizer.compile(
        base_classifier,
        trainset=train_examples,
        valset=val_examples
    )
    elapsed = time.time() - start_time
    
    logger.info(f"✓ Optimization complete in {elapsed:.1f}s")
    
    return optimized_classifier


def optimize_with_random_search(
    train_examples: List[Any],
    val_examples: List[Any],
    metric: Callable = classification_accuracy,
    max_bootstrapped_demos: int = 5,
    max_labeled_demos: int = 8,
    num_candidate_programs: int = 10,
    num_threads: int = 1,
    use_cot: bool = True
) -> dspy.Module:
    """Optimize using BootstrapFewShot with random search.
    
    This tries multiple random demo configurations and selects the best.
    More thorough but slower than basic BootstrapFewShot.
    
    Args:
        train_examples: Training examples
        val_examples: Validation examples
        metric: Evaluation metric function
        max_bootstrapped_demos: Max examples to include in prompts
        max_labeled_demos: Max examples to consider
        num_candidate_programs: Number of random configurations to try
        num_threads: Number of parallel threads
        use_cot: If True, use ChainOfThought reasoning
        
    Returns:
        Optimized classifier module
    """
    logger.info("Starting BootstrapFewShot with Random Search...")
    logger.info(f"  Candidates: {num_candidate_programs}")
    
    if not is_configured():
        configure_dspy_lm()
    
    base_classifier = EmailClassifierModule(use_cot=use_cot)
    
    optimizer = BootstrapFewShotWithRandomSearch(
        metric=metric,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
        num_candidate_programs=num_candidate_programs,
        num_threads=num_threads
    )
    
    start_time = time.time()
    optimized_classifier = optimizer.compile(
        base_classifier,
        trainset=train_examples,
        valset=val_examples
    )
    elapsed = time.time() - start_time
    
    logger.info(f"✓ Random search optimization complete in {elapsed:.1f}s")
    
    return optimized_classifier


def optimize_with_mipro(
    train_examples: List[Any],
    val_examples: List[Any],
    metric: Callable = classification_accuracy,
    num_candidates: int = 10,
    init_temperature: float = 1.0,
    use_cot: bool = True
) -> dspy.Module:
    """Optimize using MIPRO (Multi-prompt Instruction Proposal Optimizer).
    
    MIPRO is DSPy's most advanced optimizer. It jointly optimizes:
    - Instruction text in signatures
    - Few-shot example selection
    - Example ordering
    
    Args:
        train_examples: Training examples
        val_examples: Validation examples
        metric: Evaluation metric function
        num_candidates: Number of instruction variants to try
        init_temperature: Initial temperature for generation
        use_cot: If True, use ChainOfThought reasoning
        
    Returns:
        Optimized classifier module
    """
    logger.info("Starting MIPRO optimization...")
    logger.warning("MIPRO can take 10-30 minutes for thorough optimization")
    
    if not is_configured():
        configure_dspy_lm()
    
    base_classifier = EmailClassifierModule(use_cot=use_cot)
    
    optimizer = MIPRO(
        metric=metric,
        num_candidates=num_candidates,
        init_temperature=init_temperature
    )
    
    start_time = time.time()
    optimized_classifier = optimizer.compile(
        base_classifier,
        trainset=train_examples,
        valset=val_examples
    )
    elapsed = time.time() - start_time
    
    logger.info(f"✓ MIPRO optimization complete in {elapsed:.1f}s")
    
    return optimized_classifier


def save_optimized_classifier(
    classifier: dspy.Module,
    output_path: str = "./data/optimized_classifier.json"
):
    """Save optimized classifier to disk.
    
    Args:
        classifier: Optimized classifier module
        output_path: Path to save to
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the classifier
    classifier.save(str(output_path))
    
    logger.info(f"✓ Saved optimized classifier to {output_path}")


def load_optimized_classifier(
    input_path: str = "./data/optimized_classifier.json",
    use_cot: bool = True
) -> dspy.Module:
    """Load optimized classifier from disk.
    
    Args:
        input_path: Path to load from
        use_cot: If True, use ChainOfThought module
        
    Returns:
        Loaded classifier module
    """
    if not is_configured():
        configure_dspy_lm()
    
    # Create base module
    classifier = EmailClassifierModule(use_cot=use_cot)
    
    # Load saved state
    classifier.load(input_path)
    
    logger.info(f"✓ Loaded optimized classifier from {input_path}")
    return classifier


def compare_classifiers(
    baseline: dspy.Module,
    optimized: dspy.Module,
    test_examples: List[Any],
    verbose: bool = True
) -> Dict[str, Any]:
    """Compare baseline and optimized classifiers.
    
    Args:
        baseline: Baseline classifier
        optimized: Optimized classifier
        test_examples: Test examples to evaluate on
        verbose: If True, print detailed results
        
    Returns:
        Dict with comparison results
    """
    logger.info("Evaluating baseline classifier...")
    baseline_results = evaluate_classifier(baseline, test_examples)
    
    logger.info("Evaluating optimized classifier...")
    optimized_results = evaluate_classifier(optimized, test_examples)
    
    # Calculate improvements
    improvements = {}
    for key in baseline_results:
        if isinstance(baseline_results[key], (int, float)):
            baseline_val = baseline_results[key]
            optimized_val = optimized_results[key]
            improvement = optimized_val - baseline_val
            improvements[key] = {
                'baseline': baseline_val,
                'optimized': optimized_val,
                'improvement': improvement,
                'relative_improvement': (improvement / baseline_val * 100 
                                        if baseline_val != 0 else 0)
            }
    
    if verbose:
        print("\n" + "=" * 70)
        print("BASELINE vs OPTIMIZED COMPARISON")
        print("=" * 70)
        
        for metric, values in improvements.items():
            print(f"\n{metric}:")
            print(f"  Baseline:  {values['baseline']:.2%}")
            print(f"  Optimized: {values['optimized']:.2%}")
            print(f"  Change:    {values['improvement']:+.2%} "
                  f"({values['relative_improvement']:+.1f}%)")
        
        print("=" * 70 + "\n")
    
    return {
        'baseline': baseline_results,
        'optimized': optimized_results,
        'improvements': improvements
    }


def main():
    """CLI for running optimization."""
    import argparse
    from evaluation.create_dataset import load_dataset
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="Optimize DSPy email classifier")
    parser.add_argument('--train-data', required=True,
                       help='Path to training dataset (JSON)')
    parser.add_argument('--val-data', required=True,
                       help='Path to validation dataset (JSON)')
    parser.add_argument('--output', default='./data/optimized_classifier.json',
                       help='Output path for optimized classifier')
    parser.add_argument('--optimizer', choices=['bootstrap', 'random_search', 'mipro'],
                       default='bootstrap',
                       help='Optimization algorithm to use')
    parser.add_argument('--metric', choices=['accuracy', 'weighted', 'combined'],
                       default='accuracy',
                       help='Optimization metric')
    parser.add_argument('--max-demos', type=int, default=5,
                       help='Maximum few-shot examples in prompts')
    parser.add_argument('--no-cot', action='store_true',
                       help='Disable chain-of-thought reasoning')
    
    args = parser.parse_args()
    
    # Load datasets
    print(f"Loading training data from {args.train_data}...")
    train_examples = load_dataset(args.train_data)
    
    print(f"Loading validation data from {args.val_data}...")
    val_examples = load_dataset(args.val_data)
    
    if not train_examples or not val_examples:
        print("Error: No examples found in datasets")
        return
    
    # Select metric
    metric_map = {
        'accuracy': classification_accuracy,
        'weighted': weighted_accuracy,
        'combined': combined_metric
    }
    metric = metric_map[args.metric]
    
    # Run optimization
    use_cot = not args.no_cot
    
    if args.optimizer == 'bootstrap':
        optimized = optimize_with_bootstrap_fewshot(
            train_examples, val_examples,
            metric=metric,
            max_bootstrapped_demos=args.max_demos,
            use_cot=use_cot
        )
    elif args.optimizer == 'random_search':
        optimized = optimize_with_random_search(
            train_examples, val_examples,
            metric=metric,
            max_bootstrapped_demos=args.max_demos,
            use_cot=use_cot
        )
    elif args.optimizer == 'mipro':
        optimized = optimize_with_mipro(
            train_examples, val_examples,
            metric=metric,
            use_cot=use_cot
        )
    
    # Save optimized classifier
    save_optimized_classifier(optimized, args.output)
    
    # Evaluate and compare
    print("\nEvaluating optimized classifier...")
    baseline = EmailClassifierModule(use_cot=use_cot)
    compare_classifiers(baseline, optimized, val_examples, verbose=True)
    
    print(f"\n✓ Optimization complete!")
    print(f"✓ Saved to: {args.output}")
    print(f"\nTo use the optimized classifier:")
    print(f"  1. Set USE_DSPY=true in your environment")
    print(f"  2. Run: python gmail_categorizer.py")


if __name__ == "__main__":
    main()
