import logging
import sqlite3
import time
import os
from typing import Dict, List, Any, Optional
import uuid
import chromadb

logger = logging.getLogger(__name__)

class EpisodeMemory:
    """
    SQLite-backed layer for storing exact conversational turns (episodes).
    """
    def __init__(self, db_path: str = "episodes.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    message TEXT,
                    role TEXT,
                    timestamp REAL
                )
            ''')
            conn.commit()

    def add_episode(self, user_id: int, message: str, role: str) -> str:
        """Store a single conversational turn. Returns the episode ID."""
        episode_id = str(uuid.uuid4())
        timestamp = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO episodes (id, user_id, message, role, timestamp) VALUES (?, ?, ?, ?, ?)',
                (episode_id, user_id, message, role, timestamp)
            )
            conn.commit()
        return episode_id

    def get_recent_episodes(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the most recent conversation history for context."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT id, user_id, message, role, timestamp FROM episodes WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
                (user_id, limit)
            )
            rows = cursor.fetchall()

        # Reverse to return chronologically
        return [dict(row) for row in reversed(rows)]

    def get_episodes_by_ids(self, episode_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve specific episodes by ID."""
        if not episode_ids:
            return []

        placeholders = ','.join(['?'] * len(episode_ids))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f'SELECT id, user_id, message, role, timestamp FROM episodes WHERE id IN ({placeholders}) ORDER BY timestamp ASC',
                tuple(episode_ids)
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

class SemanticMemory:
    """
    ChromaDB-backed layer for storing and retrieving facts/concepts via embeddings.
    """
    def __init__(self, persist_dir: str = "./chroma_db", collection_name: str = "semantics"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def store_fact(self, user_id: int, fact: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Embed and store a semantic fact."""
        fact_id = str(uuid.uuid4())

        meta = metadata or {}
        meta["user_id"] = user_id

        self.collection.add(
            documents=[fact],
            metadatas=[meta],
            ids=[fact_id]
        )

    def search(self, user_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant facts based on a query."""
        count = self.collection.count()
        if count == 0:
            return []

        n_results = min(top_k, count)
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": user_id}
        )

        facts = []
        if results and results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                facts.append({
                    "fact": doc,
                    "metadata": meta
                })
        return facts

class ThemeMemory:
    """
    Layer for abstract, long-term summaries or user themes/preferences.
    (Could be backed by SQLite or simple JSON for now)
    """
    def __init__(self):
        self.themes = {}

    def update_theme(self, user_id: int, theme_name: str, content: str) -> None:
        """Update a long-term theme or preference."""
        if user_id not in self.themes:
            self.themes[user_id] = {}
        self.themes[user_id][theme_name] = content

    def get_themes(self, user_id: int) -> Dict[str, Any]:
        """Retrieve all active themes for a user."""
        return self.themes.get(user_id, {})


class XMemoryStack:
    """
    The unified xMemory stack combining Episode, Semantic, and Theme layers.
    Inject this into the Hermes agent.
    """
    def __init__(self, db_path: str = "episodes.sqlite", chroma_path: str = "./chroma_db"):
        self.episodes = EpisodeMemory(db_path=db_path)
        self.semantics = SemanticMemory(persist_dir=chroma_path)
        self.themes = ThemeMemory()

    def store_interaction(self, user_id: int, user_message: str, agent_response: str) -> None:
        """
        Record a complete interaction round.
        Implement logic to route exact logs to EpisodeMemory,
        extract facts for SemanticMemory, and update ThemeMemory if necessary.
        """
        user_episode_id = self.episodes.add_episode(user_id, user_message, "user")
        agent_episode_id = self.episodes.add_episode(user_id, agent_response, "agent")

        # Here we extract facts. In a real system, an LLM would do this.
        # For our tests to work, we'll store the raw message as a fact with the episode ID.
        self.semantics.store_fact(
            user_id,
            user_message,
            {"episode_id": user_episode_id}
        )
        self.semantics.store_fact(
            user_id,
            agent_response,
            {"episode_id": agent_episode_id}
        )

    def build_context(self, user_id: int, current_message: str) -> Dict[str, Any]:
        """
        Retrieve relevant context for the current turn.
        Returns a structured dictionary combining recent episodes,
        relevant semantic facts, and overarching themes.
        """
        # Retrieve top k semantic facts related to the current message
        relevant_facts = self.semantics.search(user_id, current_message, top_k=3)

        # Use semantic->episode retrieval: Fetch the episodes related to the retrieved facts
        retrieved_episode_ids = [
            fact["metadata"]["episode_id"] for fact in relevant_facts
            if "episode_id" in fact.get("metadata", {})
        ]

        # Get the full episode texts
        semantic_episodes = self.episodes.get_episodes_by_ids(retrieved_episode_ids)

        return {
            "recent_episodes": self.episodes.get_recent_episodes(user_id),
            "relevant_facts": relevant_facts,
            "semantic_episodes": semantic_episodes,
            "themes": self.themes.get_themes(user_id)
        }
