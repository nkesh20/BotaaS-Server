#!/usr/bin/env python3
"""
Test script for the ToxicityDetector service
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.toxicity_detector import ToxicityDetector

def test_toxicity_detector():
    """Test the toxicity detector with various inputs"""
    
    print("Initializing ToxicityDetector...")
    detector = ToxicityDetector()
    
    # Test cases
    test_cases = [
        "შენ დებილი ხომ არ ხარ?",
        "ამძიმებ დედამიწას!",
        "კარგია, ყოჩაღ!",
        "ცოტა ტვინი დააყოლე!",
        "არაუშავს, მაინც კარგია.",
        
        "შე ჩათლახო, შენა!",
        "ჩემო საყვარელო!",
        "ტვინი არ გაქვს?",
        "ასეთი სულელი როგორ ხარ?",
        "ძალიან მეწყინა.",
    ]
    
    print("\nTesting toxicity detection:")
    print("-" * 60)
    
    for text in test_cases:
        is_toxic, confidence = detector.is_toxic(text)
        status = "TOXIC" if is_toxic else "SAFE"
        print(f"Text: '{text}'")
        print(f"Result: {status} (confidence: {confidence:.4f})")
        print("-" * 60)
    
    print("\nTesting batch processing:")
    print("-" * 60)
    
    # Test batch processing
    results = detector.batch_is_toxic(test_cases[:5])
    for i, (text, (is_toxic, confidence)) in enumerate(zip(test_cases[:5], results)):
        status = "TOXIC" if is_toxic else "SAFE"
        print(f"{i+1}. '{text}' -> {status} (confidence: {confidence:.4f})")

if __name__ == "__main__":
    test_toxicity_detector() 