import yaml
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import DirectoryReadTool, FileReadTool, WebsiteSearchTool, ScrapeWebsiteTool, EXASearchTool

from pydantic import BaseModel
# Define a Pydantic model for venue details
# (demonstrating Output as Pydantic)
class PodcastContent(BaseModel):
    title: str
    description: str
    prompt: str
    audio_link:str
    paper_link:str

class PapersList(BaseModel):
    title: str
    description: str
    paper_link:str

class ChosenPaper(BaseModel):
    title: str
    description: str
    paper_link:str


@CrewBase
class AIPaperCrew:
    """AI Paper Podcast Crew"""

    agents_config = "config/aipaper_agents.yaml"
    tasks_config = "config/aipaper_tasks.yaml"

    @agent
    def paper_finder_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["paper_finder_agent"],
            allow_delegation=False,
            verbose=True,
        )

    @agent
    def researcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher_agent"],
            allow_delegation=False,
            verbose=True,
        )

    @agent
    def writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["writer_agent"],
            allow_delegation=False,
            verbose=True,
        )

    @task
    def find_papers_task(self) -> Task:
        return Task(
            config=self.tasks_config["find_paper_task"],
            tools=[EXASearchTool()],
            agent=self.paper_finder_agent(),
            output_json=PapersList,
            output_file="papers_list.json",
        )
    
    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],
            agent=self.researcher_agent(),
            output_json=ChosenPaper,
            output_file="chosen_paper.json",
        )

    @task
    def generate_podcast_content_task(self) -> Task:
        return Task(
            config=self.tasks_config["write_task"],
            tools=[ScrapeWebsiteTool()],
            output_json=PodcastContent,
            output_file="podcast_content.json",
            agent=self.writer_agent(),
        )

    @crew
    def find_papers_crew(self) -> Crew:
        """Creates the AIPaper crew"""
        return Crew(
            agents=[self.paper_finder_agent()],
            tasks=[self.find_papers_task()],
            process=Process.sequential,
            verbose=True,
            planning=True
        ) 

    def generate_podcast_content_crew(self) -> Crew:
        """Creates the AIPaper crew"""
        return Crew(
            agents=[self.researcher_agent(),self.writer_agent()],
            tasks=[self.research_task(),self.generate_podcast_content_task()],
            process=Process.sequential,
            verbose=True,
            planning=True
        ) 