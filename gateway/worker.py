import argparse
import json
import logging
import sys
import os

# Set up paths so we can import from the main hermes packages
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from agent.xmemory import XMemoryStack

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model Configuration for OpenRouter
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "openrouter/anthropic/claude-3-haiku")
CHAIN_MODEL = os.getenv("CHAIN_MODEL", "openrouter/anthropic/claude-3.5-sonnet")

def main():
    parser = argparse.ArgumentParser(description="Hermes Agent Worker")
    parser.add_argument("--in-file", required=True, help="Input JSON file containing message context")
    parser.add_argument("--out-file", required=True, help="Output JSON file for agent response")

    args = parser.parse_args()

    try:
        with open(args.in_file, 'r') as f:
            data = json.load(f)

        user_id = data.get("user_id")
        text = data.get("text")

        logger.info(f"Worker processing message from {user_id}: {text}")

        # Initialize the xMemory stack
        memory_stack = XMemoryStack()

        # Build context for the current turn
        context = memory_stack.build_context(user_id, text)

        # NOTE: OpenRouter Model Configuration
        # Hermes uses litellm under the hood. By prefixing the models with "openrouter/",
        # litellm automatically maps the API calls to OpenRouter endpoints, provided
        # that the OPENROUTER_API_KEY environment variable is set.
        #
        # Example pseudo-code for how this is typically routed in Hermes:
        #
        # intent = agent.analyze_intent(model=ROUTER_MODEL, prompt=text)
        # if intent == "complex_task":
        #     response_text = agent.execute_chain(model=CHAIN_MODEL, context=context)
        # else:
        #     response_text = agent.simple_reply(model=ROUTER_MODEL, context=context)

        response_text = f"Hello {user_id}! You said: {text}\n(Agent and xMemory integration pending)\nConfigured Routing: {ROUTER_MODEL}\nConfigured Chain: {CHAIN_MODEL}"

        # Store the interaction asynchronously/synchronously
        memory_stack.store_interaction(user_id, text, response_text)

        with open(args.out_file, 'w') as f:
            json.dump({"response": response_text}, f)

    except Exception as e:
        logger.error(f"Worker encountered error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
