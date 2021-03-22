import scraping
import jinja2
import frontmatter
import yaml
import typer
import typing as T

def main(template_path: str, result_path: T.Optional[str] = None) -> None:
    # obtain scraper and template definition
    scraper_dict = frontmatter.load(template_path).to_dict()
    content = scraper_dict.pop('content')
    # parse the scraper and evaluate it
    scraper = scraping.Scraper(scraper_dict)
    data = scraper.evaluate()
    # render the template
    templ = jinja2.Template(content)
    result = templ.render(data)
    # output the results
    if result_path is None:
        print(result)
    else:
        with open(result_path, 'w') as f:
            f.write(result)

if __name__ == "__main__":
    typer.run(main)
