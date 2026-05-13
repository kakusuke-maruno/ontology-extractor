import click
import asyncio
import logging
from ontology_extractor.neo4j_client import OntologyPipeline

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

@click.group()
def cli():
    """Ontology Extractor CLI: Extract ontology schema from text."""
    pass

async def _extract_async(text_file):
    click.echo(f"Processing {text_file} for ontology extraction...")
    
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    click.echo("Connecting to Neo4j and initializing LLM pipeline...")
    
    pipeline = None
    try:
        pipeline = OntologyPipeline()
        click.echo("Generating and storing ontology schema via Local LLM...")
        await pipeline.run(content)
        click.secho("Successfully extracted and stored ontology schema in Neo4j!", fg="green")
    except Exception as e:
        click.secho(f"Failed to process pipeline: {e}", fg="red")
    finally:
        if pipeline:
            await pipeline.close()

@cli.command()
@click.argument('text_file', type=click.Path(exists=True))
def extract(text_file):
    """Extract ontology schema from a text file and store it in Neo4j."""
    asyncio.run(_extract_async(text_file))

async def _populate_async(text_file):
    click.echo(f"Processing {text_file} for Knowledge Graph population...")
    
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    click.echo("Connecting to Neo4j and initializing LLM pipeline...")
    
    pipeline = None
    try:
        pipeline = OntologyPipeline()
        click.echo("Generating and storing knowledge graph via Local LLM...")
        await pipeline.populate_kg(content)
        click.secho("Successfully extracted and stored knowledge graph in Neo4j!", fg="green")
    except Exception as e:
        click.secho(f"Failed to process pipeline: {e}", fg="red")
    finally:
        if pipeline:
            await pipeline.close()

@cli.command()
@click.argument('text_file', type=click.Path(exists=True))
def populate(text_file):
    """Extract knowledge graph instances from a text file based on the stored ontology schema."""
    asyncio.run(_populate_async(text_file))

async def _ask_async(question):
    click.echo(f"Querying Knowledge Graph for: '{question}'...")
    
    pipeline = None
    try:
        pipeline = OntologyPipeline()
        answer = await pipeline.query_kg(question)
        click.echo("\n--- Answer ---")
        click.secho(answer, fg="cyan")
        click.echo("--------------\n")
    except Exception as e:
        click.secho(f"Failed to process pipeline: {e}", fg="red")
    finally:
        if pipeline:
            await pipeline.close()

@cli.command()
@click.argument('question', type=str)
def ask(question):
    """Ask a question to the Knowledge Graph using GraphRAG."""
    asyncio.run(_ask_async(question))

if __name__ == '__main__':
    cli()
