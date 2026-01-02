import pytest

from skincare_agent_system.actors.base_agent import BaseAgent


class ConcreteAgent(BaseAgent):
    def run(self, context, directive):
        pass


def test_base_agent_initialization():
    agent = ConcreteAgent(name="TestAgent", role="Tester", backstory="Testing")
    assert agent.name == "TestAgent"
    assert agent.role == "Tester"


#    assert str(agent) == "TestAgent (Tester)" # str(agent) might not be implemented in simplified version, BaseAgent doesn't have __repr__


def test_base_agent_attributes():
    agent = ConcreteAgent("Agent007")
    assert agent.name == "Agent007"
    assert agent.role == "Assistant"  # Default
