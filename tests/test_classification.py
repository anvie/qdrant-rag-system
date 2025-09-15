#!/usr/bin/env python3
"""
Test classification using embedding models via Ollama.

This script demonstrates text classification using embedding similarity
for 4 categories: sport, islamic literature, finance, and programming.
"""

import numpy as np
from typing import List, Dict, Tuple
import sys
import os
import argparse

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.embedding.client import OllamaEmbeddingClient


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def create_test_data() -> Dict[str, List[str]]:
    """Create dummy test data for each category."""
    return {
        "sport": [
            "The football match ended with a dramatic penalty shootout",
            "Tennis player wins her third Grand Slam title this year",
            "Basketball team breaks record with 150 points in single game",
            "Olympic swimmer sets new world record in 100m freestyle",
            "Cricket world cup final attracts millions of viewers worldwide",
        ],
        "islamic": [
            "Hadith collections provide guidance for daily Muslim life",
            "Islamic scholars discuss the importance of Tafsir studies",
            "Is it true that the biography of Prophet Muhammad offers valuable lessons?",
        ],
        "hukum": ["apa hukumnya makan kepiting?"],
        "quran": [
            "The interpretation of Quranic verses requires deep knowledge",
            "pada ayat berapa nabi musa menerima wahyu di gunung sinai?",
        ],
        "hadits": [
            "sebutkan hadits tentang keutamaan sedekah",
            "apa kata Rasulullah tentang pentingnya ilmu? Dan diriwayatkan oleh siapa?",
        ],
        "finance": [
            "Stock market reaches all-time high amid economic recovery",
            "Central bank announces interest rate hike to combat inflation",
            "Cryptocurrency regulations impact digital asset investments",
            "Portfolio diversification strategies for long-term growth",
            "Financial analysts predict recession in coming quarters",
            "saham apa yang bagus untuk investasi jangka panjang?",
        ],
        "programming": [
            "Python's async/await pattern improves concurrent programming",
            "Machine learning frameworks simplify neural network implementation",
            "Docker containers provide consistent deployment environments",
            "Git branching strategies for effective team collaboration",
            "API design patterns for scalable microservices architecture",
            "buatkan kode python untuk menghitung faktorial",
        ],
    }


def format_text_for_model(text: str, model: str, is_category: bool = False) -> str:
    """
    Format text based on the model requirements.

    Args:
        text: The text to format
        model: The model name
        is_category: Whether this is a category label (for some models this matters)

    Returns:
        Formatted text string
    """
    # EmbeddingGemma uses special classification format
    if "embeddinggemma" in model.lower():
        return f"task: classification | query: {text}"
    # BGE models and others use plain text
    else:
        return text


def classify_text(
    text: str,
    category_embeddings: Dict[str, List[float]],
    client: OllamaEmbeddingClient,
    model: str,
) -> List[Tuple[str, float]]:
    """
    Classify text into one of the categories.

    Returns:
        List of tuples (category, confidence_score) sorted by confidence
    """
    # Format text based on model requirements
    formatted_text = format_text_for_model(text, model)

    # Get embedding for the text
    try:
        text_embedding = client.embed_text(formatted_text, model)
    except Exception as e:
        print(f"Error embedding text: {e}")
        return [("unknown", 0.0)]

    # Calculate similarity with each category
    similarities = {}
    for category, category_embedding in category_embeddings.items():
        similarity = cosine_similarity(text_embedding, category_embedding)
        similarities[category] = similarity

    # Sort categories by similarity and return top results
    sorted_categories = sorted(similarities.items(), key=lambda x: x[1], reverse=True)

    return sorted_categories


def create_confusion_matrix(
    true_labels: List[str], predicted_labels: List[str], categories: List[str]
) -> np.ndarray:
    """Create a confusion matrix."""
    n_categories = len(categories)
    matrix = np.zeros((n_categories, n_categories), dtype=int)

    category_to_idx = {cat: idx for idx, cat in enumerate(categories)}

    for true, pred in zip(true_labels, predicted_labels):
        if true in category_to_idx and pred in category_to_idx:
            matrix[category_to_idx[true]][category_to_idx[pred]] += 1

    return matrix


def print_confusion_matrix(matrix: np.ndarray, categories: List[str]):
    """Print a formatted confusion matrix."""
    print("\n" + "=" * 60)
    print("CONFUSION MATRIX")
    print("=" * 60)

    # Print header
    print(f"{'True/Predicted':<20}", end="")
    for cat in categories:
        print(f"{cat[:15]:<15}", end="")
    print()
    print("-" * (20 + 15 * len(categories)))

    # Print rows
    for i, true_cat in enumerate(categories):
        print(f"{true_cat:<20}", end="")
        for j in range(len(categories)):
            print(f"{matrix[i][j]:<15}", end="")
        print()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test text classification using Ollama embedding models"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="embeddinggemma:latest",
        help="Embedding model to use (default: embeddinggemma:latest)",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://192.168.1.7:11434",
        help="Ollama service URL (default: http://192.168.1.7:11434)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available embedding models and exit",
    )
    return parser.parse_args()


def main():
    """Main function to run classification tests."""
    args = parse_arguments()

    # Initialize Ollama client
    client = OllamaEmbeddingClient(ollama_url=args.ollama_url)

    # Check if Ollama is running
    if not client.health_check():
        print("❌ Error: Ollama service is not running.")
        print(f"Please ensure Ollama is running at: {args.ollama_url}")
        return

    # List models if requested
    if args.list_models:
        print("Available models:")
        models = client.get_available_models()
        for model in models:
            print(f"  - {model.get('name', 'unknown')}")
        return

    model = args.model

    print("=" * 60)
    print(f"TEXT CLASSIFICATION WITH {model.upper()}")
    print("=" * 60)

    print(f"✓ Connected to Ollama at {args.ollama_url}")
    print(f"✓ Using model: {model}")

    # Define categories
    categories = [
        "sport",
        "islamic",
        "finance",
        "programming",
        "hukum",
        "hadits",
        "quran",
    ]

    # Create category embeddings
    print("\nCreating category embeddings...")
    category_embeddings = {}

    for category in categories:
        formatted_category = format_text_for_model(category, model, is_category=True)
        try:
            embedding = client.embed_text(formatted_category, model)
            category_embeddings[category] = embedding
            print(f"✓ Embedded category: {category}")
        except Exception as e:
            print(f"❌ Error embedding category '{category}': {e}")
            return

    # Get test data
    test_data = create_test_data()

    # Run classification tests
    print("\n" + "=" * 60)
    print("CLASSIFICATION RESULTS")
    print("=" * 60)

    true_labels = []
    predicted_labels = []
    correct_predictions = 0
    total_predictions = 0

    for true_category, texts in test_data.items():
        print(f"\n[{true_category.upper()}]")
        for text in texts:
            classification_results = classify_text(
                text, category_embeddings, client, model
            )

            # Get the top prediction for accuracy calculation
            predicted_category = classification_results[0][0]

            true_labels.append(true_category)
            predicted_labels.append(predicted_category)

            is_correct = predicted_category == true_category
            if is_correct:
                correct_predictions += 1
            total_predictions += 1

            # Print result
            status = "✓" if is_correct else "✗"
            print(f'{status} Text: "{text[:60]}..."')

            # Print top 3 predictions
            print("  → Top 3 predictions:")
            for i, (category, confidence) in enumerate(classification_results[:3]):
                rank_marker = "★" if i == 0 else " "
                correct_marker = "✓" if category == true_category else " "
                print(
                    f"    {rank_marker} {i + 1}. {category:<20} (confidence: {confidence:.3f}) {correct_marker}"
                )

            if not is_correct:
                print(f"  → Actual category: {true_category}")

    # Calculate and display accuracy
    accuracy = correct_predictions / total_predictions * 100
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total samples: {total_predictions}")
    print(f"Correct predictions: {correct_predictions}")
    print(f"Accuracy: {accuracy:.1f}%")

    # Display confusion matrix
    matrix = create_confusion_matrix(true_labels, predicted_labels, categories)
    print_confusion_matrix(matrix, categories)

    # Display per-category accuracy
    print("\n" + "=" * 60)
    print("PER-CATEGORY ACCURACY")
    print("=" * 60)
    for i, category in enumerate(categories):
        category_total = matrix[i].sum()
        if category_total > 0:
            category_correct = matrix[i][i]
            category_accuracy = category_correct / category_total * 100
            print(
                f"{category:<20}: {category_accuracy:>5.1f}% ({category_correct}/{category_total})"
            )


if __name__ == "__main__":
    main()
