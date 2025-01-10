import scraping
import yaml
import json
import typer

def load_yaml_file(path: str) -> dict:
    with open(path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def main(scraper_path: str) -> None:
    scraper_dict = load_yaml_file(scraper_path)
    scraper = scraping.Scraper(scraper_dict)
    result = scraper.evaluate()
    print(json.dumps(result))

if __name__ == "__main__":
    typer.run(main)
