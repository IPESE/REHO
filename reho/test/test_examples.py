import os
import requests


def test_examples():
    def process_directory(api_url, local_dir):

        def download_file(file_url, local_path):
            response = requests.get(file_url)
            if response.status_code == 200:
                with open(local_path, 'wb') as file_out:
                    file_out.write(response.content)
                print(f"Downloaded {file_url} to {local_path}")
            else:
                print(f"Failed to download {file_url}: {response.status_code}")

        response = requests.get(api_url)
        if response.status_code != 200:
            print(f"Failed to fetch directory listing: {response.status_code}")
            return

        items = response.json()
        for item in items:
            item_name = item['name']
            item_path = os.path.join(local_dir, item_name)
            if item['type'] == 'file':
                raw_url = item['download_url']
                download_file(raw_url, item_path)
            elif item['type'] == 'dir':
                os.makedirs(item_path, exist_ok=True)
                process_directory(item['url'], item_path)

    def execute_scripts(directory):
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    print(f"Executing {file_path}...")
                    os.system(f"python {file_path}")

    base_api_url = "https://api.github.com/repos/IPESE/REHO/contents/scripts/examples"
    examples_dir = "examples"

    # Create local directory if it doesn't exist
    os.makedirs(examples_dir, exist_ok=True)

    # Process the directory
    process_directory(base_api_url, examples_dir)

    # Execute all Python scripts
    execute_scripts(examples_dir)
