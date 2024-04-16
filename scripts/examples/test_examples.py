import os
import subprocess


def test_run_examples_without_errors():
    test_succeeded = True
    test_script = os.path.abspath(__file__)  # Get the absolute path of this test script
    for filename in os.listdir(os.getcwd()):
        if filename.endswith(".py") and filename != os.path.basename(test_script):  # Check if the file is a Python file and also not the test script itself
            example_file = os.path.join(os.getcwd(), filename)
            print(f"Running example: {example_file}")
            try:
                # Run the file as a separate process
                subprocess.run(["python", example_file], check=True)
            except subprocess.CalledProcessError as e:
                test_succeeded = False
                print(f"Execution of {filename} failed with error: {e}")
    if not test_succeeded:
        assert False

if __name__ == "__main__":
    test_run_examples_without_errors()
