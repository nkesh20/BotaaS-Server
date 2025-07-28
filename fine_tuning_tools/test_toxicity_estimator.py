import sys
import os

# Add the parent directory to the Python path so we can import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.toxicity_estimator import ToxicityEstimator, get_toxicity_estimator

def test_toxicity_estimator():
    print("Initializing ToxicityEstimator...")
    estimator = get_toxicity_estimator()
    
    # Test cases
    test_cases = [
        "I hate you so much",
        "Thanks for your help",
        "You're a complete idiot and I hope you fail",
        "The weather is nice today",
        "Go to hell you worthless piece of trash",
        "არაუშავს, მერე რა მოხდა?",
        "მეც მასე ვფიქრობ",
        "წადი შენი შე ნაბიჭვარო",
        "მიგაკლავთ შენც და იმასაც",
        "დილა მშვიდობისა",
    ]
    
    print("\nTesting toxicity estimation:")
    print("-" * 60)
    
    for text in test_cases:
        toxicity = estimator.get_toxicity(text)
        print(f"Text: '{text}'")
        print(f"Toxicity: {toxicity:.4f}")
        print("-" * 60)
    
    print("\nTesting batch processing:")
    print("-" * 60)

if __name__ == "__main__":
    test_toxicity_estimator() 