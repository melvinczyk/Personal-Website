from django.test import TestCase

# Create your tests here.

if __name__ == "__main__":
    accuracies = [
        82.71, 83.51, 86.69, 73.71, 79.46, 85.20, 76.41, 83.39, 79.12,
        78.52, 80.00, 81.35, 90.14, 83.10, 95.39, 85.82, 100.00, 80.60,
        59.00, 77.33, 75.29, 69.00, 77.94, 79.91, 74.81, 75.82, 73.60,
        71.00, 78.27, 82.41
    ]

    total_accuracy = sum(accuracies) / len(accuracies)
    print(total_accuracy)
