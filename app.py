
import os
from uuid import uuid4
from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.agents import AgentType
from langchain.llms import OpenAI
from langchain.agents import ZeroShotAgent, Tool, AgentExecutor
from langchain import OpenAI, SerpAPIWrapper, LLMChain
from typing import List, Dict, Callable
from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts.prompt import PromptTemplate
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
) 
unique_id = uuid4().hex[0:8]
import streamlit as st 
from langchain.utilities import GoogleSerperAPIWrapper 


os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY')
OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY')

os.environ['SERPER_API_KEY'] = os.environ.get('SERPER_API_KEY')
SERPER_API_KEY=os.environ.get('SERPER_API_KEY')

llm = OpenAI(temperature=0,model_name='gpt-4')
#llm = OpenAI(temperature=0)


class DialogueAgent:
    def __init__(
        self,
        name: str,
        system_message: SystemMessage,
        model: ChatOpenAI,
    ) -> None:
        self.name = name
        self.system_message = system_message
        self.model = model
        self.prefix = f"{self.name}: "
        self.reset()

    def reset(self):
        self.message_history = ["Here is the conversation so far."]

    def send(self) -> str:
        """
        Applies the chatmodel to the message history
        and returns the message string
        """
        message = self.model(
            [
                self.system_message,
                HumanMessage(content="\n".join(self.message_history + [self.prefix])),
            ]
        )
        return message.content

    def receive(self, name: str, message: str) -> None:
        """
        Concatenates {message} spoken by {name} into message history
        """
        self.message_history.append(f"{name}: {message}")



class DialogueSimulator:
    def __init__(
        self,
        agents: List[DialogueAgent],
        selection_function: Callable[[int, List[DialogueAgent]], int] ) -> None:
        
        self.agents = agents
        self._step = 0
        self.select_next_speaker = selection_function

    def reset(self):
        for agent in self.agents:
            agent.reset()

    def inject(self, name: str, message: str):
        """
        Initiates the conversation with a {message} from {name}
        """
        for agent in self.agents:
            agent.receive(name, message)

        # increment time
        self._step += 1

    def step(self) -> tuple[str, str]:
        # 1. choose the next speaker
        speaker_idx = self.select_next_speaker(self._step, self.agents)
        speaker = self.agents[speaker_idx]

        # 2. next speaker sends message
        message = speaker.send()

        # 3. everyone receives message
        for receiver in self.agents:
            receiver.receive(speaker.name, message)

        # 4. increment time
        self._step += 1

        return speaker.name, message
    

gsearch = GoogleSerperAPIWrapper()
search_tools = [
    Tool(
        name="Intermediate Answer",
        func=gsearch.run,
        description="useful for when you need to ask with search"
    )
]
    
class DialogueAgentWithTools(DialogueAgent):
    def __init__(
        self,
        name: str,
        system_message: SystemMessage,
        model: ChatOpenAI,
        tool_names: List[str],
        **tool_kwargs,
    ) -> None:
        super().__init__(name, system_message, model)
        self.tools = load_tools(tool_names, **tool_kwargs)

    def send(self) -> str:
        """
        Applies the chatmodel to the message history
        and returns the message string
        """
        agent_chain = initialize_agent(
            #self.tools,
            search_tools,
            self.model,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            verbose=True,
            memory=ConversationBufferMemory(
                memory_key="chat_history", return_messages=True
            ),
        )
        message = AIMessage(
            content=agent_chain.run(
                input="\n".join(
                    [self.system_message.content] + self.message_history + [self.prefix]
                )
            )
        )

        return message.content
    
def generate_agent_description(name):
    agent_specifier_prompt = [
        agent_descriptor_system_message,
        HumanMessage(
            content=f"""{conversation_description}
            Please reply with a creative description of {name}, in {word_limit} words or less. 
            Speak directly to {name}.
            Give them a point of view.
            Do not add anything else."""
        ),
    ]
    agent_description = ChatOpenAI(temperature=1.0)(agent_specifier_prompt).content
    return agent_description

def generate_system_message(name, description, tools,preferences):
    return f"""{conversation_description}
    
    Your name is {name}.

    Your description is as follows: {description}

    
    Your goal is to persuade your conversation partner of your point of view.
    you need to talk based on the {','.join(preferences)} for {name}


    DO look up information with your tool to refute your partner's claims.
    DO cite your sources.

    DO NOT fabricate fake citations.
    DO NOT cite any source that you did not look up.

    Do not add anything else.

    Stop speaking the moment you finish speaking from your perspective.
    """

def select_next_speaker(step: int, agents: List[DialogueAgent]) -> int:
    idx = (step) % len(agents)
    return idx




if __name__ == '__main__':


    st.title("Discover your perfect getaway based on your interests!")

    # Input fields (corrected placement)
    city1 = st.text_input("City1")
    city2 = st.text_input("City2")

    # Preference dropdown
    preference_options = [
        "Cultural Exploration",
        "Adventurous Escape",
        "Relaxation and Rejuvenation",
        "Foodie Delights",
        "Nightlife and Entertainment",
        "Romantic Getaway",
        "Family Fun",
        "Budget Travel",
    ]

    #preference = st.selectbox("Select your vacation preference:", preference_options)
    preferences = st.multiselect("Select Your Preferences", preference_options)
    print(preferences)
   
    # Submit button
    if st.button("Submit"):
        # Get program response

        names = {city1: ["arxiv", "wikipedia"],city2: ["arxiv", "wikipedia"]}
        topic = "Find the best city for next vacation based on {}".format(','.join(preferences))
        word_limit = 10  # word limit for task brainstorming

        conversation_description = f"""Here is the topic of conversation: {topic} The participants are: {', '.join(names.keys())}"""

        agent_descriptor_system_message = SystemMessage(
            content="You can add detail to the description of the conversation participant."
        )

        agent_descriptions = {name: generate_agent_description(name) for name in names}

        agent_system_messages = {name: generate_system_message(name, description, tools,preferences) for (name, tools), description in zip(names.items(), agent_descriptions.values())}

        topic_specifier_prompt = [
        SystemMessage(content="You can make a topic more specific."),
        HumanMessage(
        content=f"""{topic}
        
        You are the moderator.
        Please make the topic more specific.
        Please reply with the specified quest in {word_limit} words or less. 
        Speak directly to the participants: {*names,}.
        Do not add anything else."""
        ),
        ]
        
        specified_topic = ChatOpenAI(temperature=1.0)(topic_specifier_prompt).content



        # we set `top_k_results`=2 as part of the `tool_kwargs` to prevent results from overflowing the context limit
        agents = [
            DialogueAgentWithTools(
                name=name,
                system_message=SystemMessage(content=system_message),
                #model=ChatOpenAI(model_name="gpt-4", temperature=0.2),
                model=ChatOpenAI( temperature=0.5),
                tool_names=tools,
                top_k_results=2,
            )
            for (name, tools), system_message in zip(
                names.items(), agent_system_messages.values()
            )
        ]

        max_iters = 8
        n = 0


        simulator = DialogueSimulator(agents=agents, selection_function=select_next_speaker)
        simulator.reset()
        simulator.inject("Moderator", specified_topic)
        print(f"(Moderator): {specified_topic}")
        print("\n")

        conv_dict_list=[]
        while n < max_iters:
            name, message = simulator.step()
            # Display response
            #st.write("Chat between Agents")
            st.markdown(f"({name}): {message}")

            print(f"({name}): {message}")
            print("\n")
            conv_dict={name:message}
            conv_dict_list.append(conv_dict)
            n += 1
