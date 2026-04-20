import time
import os
import sys

def wait_and_run():
    print("Waiting for Phase 3 (TruthCrew) and Phase 5 (Ablation Study) to complete...")
    
    while True:
        valid_ablation = False
        valid_crew = False
        
        try:
            with open(r'evaluation\results\ablation_study.csv', 'r', encoding='utf-8') as f:
                valid_ablation = sum(1 for line in f) >= 361  # 60 claims * 6 configs + 1 header
        except Exception:
            pass

        try:
            with open(r'evaluation\results\truthcrew_predictions.csv', 'r', encoding='utf-8') as f:
                lines = sum(1 for line in f)
                valid_crew = lines >= 61 # 60 claims + 1 header
                print(f"TruthCrew lines so far: {lines-1}/60")
        except Exception:
            pass

        if valid_ablation and valid_crew:
            break
        
        time.sleep(20)

    print("\nBoth phases complete! Running Phase 6: Compute Metrics...")
    os.system(f"{sys.executable} -m evaluation.compute_metrics")
    
    print("\nRunning Phase 7: Generate Report...")
    os.system(f"{sys.executable} -m evaluation.generate_report")
    
    print("\nBenchmark Evaluation Pipeline Fully Completed!")

if __name__ == "__main__":
    wait_and_run()
