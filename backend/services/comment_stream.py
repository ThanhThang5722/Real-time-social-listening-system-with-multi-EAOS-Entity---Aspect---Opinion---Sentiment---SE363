import json
import asyncio
import random
from typing import List
from datetime import datetime
from pathlib import Path
from models.schemas import Comment, EAOSLabel


class CommentStreamService:
    """Service to simulate real-time comment streaming from filtered.json"""

    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.comments: List[dict] = []
        self.current_index = 0
        self._load_data()

    def _load_data(self):
        """Load comments from filtered.json"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.comments = data.get('results', [])
                print(f"Loaded {len(self.comments)} comments from {self.data_path}")
        except Exception as e:
            print(f"Error loading data: {e}")
            self.comments = []

    async def get_next_comment(self) -> Comment:
        """Get next comment from the dataset (循环)"""
        if not self.comments:
            # Return a mock comment if no data
            return self._generate_mock_comment()

        comment_data = self.comments[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.comments)

        # Convert to Comment model
        labels = [
            EAOSLabel(**label) for label in comment_data.get('labels', [])
        ]

        # Generate mock username
        usernames = ["user123", "viewer456", "fan789", "livestream_watcher", "comment_user"]

        return Comment(
            id=f"comment_{self.current_index}_{datetime.now().timestamp()}",
            text=comment_data['text'],
            labels=labels,
            timestamp=datetime.now(),
            username=random.choice(usernames)
        )

    def _generate_mock_comment(self) -> Comment:
        """Generate a mock comment for testing"""
        mock_texts = [
            "Chương trình rất hay và bổ ích!",
            "Diễn viên diễn xuất tốt quá!",
            "Âm thanh hơi nhỏ, không nghe rõ lắm",
            "Kịch bản phim này cuốn quá đi!",
            "Mùa này không hay bằng mùa trước"
        ]

        mock_labels = [
            EAOSLabel(
                entity="chương trình",
                aspect="Kịch bản",
                opinion="rất hay",
                sentiment="tích cực"
            )
        ]

        return Comment(
            id=f"mock_{datetime.now().timestamp()}",
            text=random.choice(mock_texts),
            labels=mock_labels,
            timestamp=datetime.now(),
            username="mock_user"
        )

    async def stream_comments(self, interval: float = 2.0):
        """Generator to stream comments at specified interval (seconds)"""
        while True:
            comment = await self.get_next_comment()
            yield comment
            await asyncio.sleep(interval)
