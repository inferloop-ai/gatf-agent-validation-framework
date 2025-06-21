"""
Basic Text Generator

This module provides template-based text generation capabilities for creating
synthetic text data for testing AI agents.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
import random
import re
from string import Template
from datetime import datetime
import json

from faker import Faker

from ...core.exceptions import DataGenerationError
from ...utils.logging import get_logger, log_performance

logger = get_logger(__name__)


class BasicTextGenerator:
    """
    Basic text generator for creating synthetic text data.
    
    This generator supports:
    - Template-based generation
    - Various text types (emails, reviews, articles, etc.)
    - Multilingual support
    - Structured text generation
    """
    
    def __init__(self, seed: Optional[int] = None, locale: str = "en_US"):
        """
        Initialize the text generator.
        
        Args:
            seed: Random seed for reproducibility
            locale: Locale for Faker (e.g., 'en_US', 'fr_FR', 'de_DE')
        """
        self.seed = seed
        self.locale = locale
        
        if seed is not None:
            random.seed(seed)
            Faker.seed(seed)
        
        self.fake = Faker(locale)
        
        # Pre-defined templates
        self._templates = self._initialize_templates()
        
    def _initialize_templates(self) -> Dict[str, List[str]]:
        """Initialize text templates."""
        return {
            "email": [
                """Subject: $subject

Dear $recipient_name,

$opening_line

$body_paragraph_1

$body_paragraph_2

$closing_line

Best regards,
$sender_name
$sender_title""",
                """Subject: RE: $subject

Hi $recipient_name,

$body_paragraph_1

Let me know if you have any questions.

Thanks,
$sender_name"""
            ],
            "review": [
                """Title: $title
Rating: $rating/5

$opening_statement

Pros:
$pros

Cons:
$cons

$conclusion

Would I recommend this? $recommendation""",
                """$rating stars - $title

$review_body

$summary"""
            ],
            "article": [
                """# $title

*By $author_name | $date*

## $subtitle

$introduction

### $section_1_title
$section_1_content

### $section_2_title
$section_2_content

### Conclusion
$conclusion

---
*Tags: $tags*"""
            ],
            "conversation": [
                """User: $user_message_1
Assistant: $assistant_response_1

User: $user_message_2
Assistant: $assistant_response_2

User: $user_message_3
Assistant: $assistant_response_3"""
            ],
            "support_ticket": [
                """Ticket #$ticket_id
Priority: $priority
Category: $category

Subject: $subject

Description:
$description

Steps to reproduce:
$steps

Expected behavior:
$expected

Actual behavior:
$actual

Customer: $customer_name
Email: $customer_email"""
            ]
        }
    
    @log_performance
    def generate(
        self,
        text_type: str,
        num_samples: int,
        template: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[str]:
        """
        Generate text samples.
        
        Args:
            text_type: Type of text to generate
            num_samples: Number of samples to generate
            template: Custom template (optional)
            variables: Custom variables for template
            **kwargs: Additional generation parameters
            
        Returns:
            List of generated text samples
        """
        if num_samples <= 0:
            raise DataGenerationError("Number of samples must be positive")
        
        samples = []
        
        for _ in range(num_samples):
            if template:
                # Use custom template
                text = self._generate_from_template(template, variables or {})
            else:
                # Use predefined template
                text = self._generate_by_type(text_type, **kwargs)
            
            samples.append(text)
        
        return samples
    
    def _generate_by_type(self, text_type: str, **kwargs) -> str:
        """Generate text based on type."""
        if text_type == "email":
            return self._generate_email(**kwargs)
        elif text_type == "review":
            return self._generate_review(**kwargs)
        elif text_type == "article":
            return self._generate_article(**kwargs)
        elif text_type == "conversation":
            return self._generate_conversation(**kwargs)
        elif text_type == "support_ticket":
            return self._generate_support_ticket(**kwargs)
        elif text_type == "paragraph":
            return self._generate_paragraph(**kwargs)
        elif text_type == "sentence":
            return self.fake.sentence()
        elif text_type == "question":
            return self._generate_question(**kwargs)
        elif text_type == "json":
            return self._generate_json(**kwargs)
        else:
            # Default to paragraph
            return self._generate_paragraph(**kwargs)
    
    def _generate_email(self, **kwargs) -> str:
        """Generate an email."""
        template = random.choice(self._templates["email"])
        
        variables = {
            "subject": kwargs.get("subject", self.fake.sentence(nb_words=6)),
            "recipient_name": kwargs.get("recipient", self.fake.name()),
            "sender_name": kwargs.get("sender", self.fake.name()),
            "sender_title": self.fake.job(),
            "opening_line": self.fake.sentence(),
            "body_paragraph_1": self.fake.paragraph(nb_sentences=3),
            "body_paragraph_2": self.fake.paragraph(nb_sentences=3),
            "closing_line": random.choice([
                "Looking forward to your response.",
                "Please let me know your thoughts.",
                "I appreciate your time and consideration.",
                "Thank you for your attention to this matter."
            ])
        }
        
        return self._generate_from_template(template, variables)
    
    def _generate_review(self, **kwargs) -> str:
        """Generate a product/service review."""
        template = random.choice(self._templates["review"])
        
        rating = kwargs.get("rating", random.randint(1, 5))
        
        # Generate pros and cons based on rating
        if rating >= 4:
            num_pros = random.randint(3, 5)
            num_cons = random.randint(0, 2)
            recommendation = "Yes"
        elif rating >= 3:
            num_pros = random.randint(2, 3)
            num_cons = random.randint(2, 3)
            recommendation = "Maybe"
        else:
            num_pros = random.randint(0, 2)
            num_cons = random.randint(3, 5)
            recommendation = "No"
        
        pros = "\n".join([f"- {self.fake.sentence()}" for _ in range(num_pros)])
        cons = "\n".join([f"- {self.fake.sentence()}" for _ in range(num_cons)])
        
        variables = {
            "title": kwargs.get("title", self.fake.catch_phrase()),
            "rating": str(rating),
            "opening_statement": self.fake.sentence(),
            "pros": pros,
            "cons": cons,
            "review_body": self.fake.paragraph(nb_sentences=5),
            "conclusion": self.fake.paragraph(nb_sentences=2),
            "summary": self.fake.sentence(),
            "recommendation": recommendation
        }
        
        return self._generate_from_template(template, variables)
    
    def _generate_article(self, **kwargs) -> str:
        """Generate an article."""
        template = random.choice(self._templates["article"])
        
        variables = {
            "title": kwargs.get("title", self.fake.catch_phrase()),
            "subtitle": self.fake.sentence(),
            "author_name": self.fake.name(),
            "date": datetime.now().strftime("%B %d, %Y"),
            "introduction": self.fake.paragraph(nb_sentences=4),
            "section_1_title": self.fake.sentence(nb_words=4),
            "section_1_content": "\n\n".join([
                self.fake.paragraph(nb_sentences=5) for _ in range(3)
            ]),
            "section_2_title": self.fake.sentence(nb_words=4),
            "section_2_content": "\n\n".join([
                self.fake.paragraph(nb_sentences=5) for _ in range(3)
            ]),
            "conclusion": self.fake.paragraph(nb_sentences=4),
            "tags": ", ".join([self.fake.word() for _ in range(5)])
        }
        
        return self._generate_from_template(template, variables)
    
    def _generate_conversation(self, **kwargs) -> str:
        """Generate a conversation."""
        template = random.choice(self._templates["conversation"])
        
        # Generate conversation turns
        topics = kwargs.get("topics", [self.fake.word() for _ in range(3)])
        
        variables = {
            "user_message_1": f"Can you tell me about {topics[0]}?",
            "assistant_response_1": self.fake.paragraph(nb_sentences=3),
            "user_message_2": f"That's interesting. What about {topics[1]}?",
            "assistant_response_2": self.fake.paragraph(nb_sentences=3),
            "user_message_3": f"How does this relate to {topics[2]}?",
            "assistant_response_3": self.fake.paragraph(nb_sentences=3)
        }
        
        return self._generate_from_template(template, variables)
    
    def _generate_support_ticket(self, **kwargs) -> str:
        """Generate a support ticket."""
        template = random.choice(self._templates["support_ticket"])
        
        priorities = ["Low", "Medium", "High", "Critical"]
        categories = ["Technical", "Billing", "Account", "Feature Request", "Bug Report"]
        
        variables = {
            "ticket_id": self.fake.uuid4()[:8].upper(),
            "priority": kwargs.get("priority", random.choice(priorities)),
            "category": kwargs.get("category", random.choice(categories)),
            "subject": kwargs.get("subject", self.fake.sentence()),
            "description": self.fake.paragraph(nb_sentences=4),
            "steps": "\n".join([
                f"{i+1}. {self.fake.sentence()}" for i in range(3)
            ]),
            "expected": self.fake.sentence(),
            "actual": self.fake.sentence(),
            "customer_name": self.fake.name(),
            "customer_email": self.fake.email()
        }
        
        return self._generate_from_template(template, variables)
    
    def _generate_paragraph(self, **kwargs) -> str:
        """Generate a paragraph."""
        num_sentences = kwargs.get("num_sentences", 5)
        topic = kwargs.get("topic")
        
        if topic:
            # Generate topic-focused paragraph
            sentences = []
            sentences.append(f"When considering {topic}, there are several important factors.")
            for _ in range(num_sentences - 2):
                sentences.append(self.fake.sentence())
            sentences.append(f"In conclusion, {topic} remains a significant consideration.")
            return " ".join(sentences)
        else:
            return self.fake.paragraph(nb_sentences=num_sentences)
    
    def _generate_question(self, **kwargs) -> str:
        """Generate a question."""
        question_types = [
            "What is {}?",
            "How does {} work?",
            "Why is {} important?",
            "When should {} be used?",
            "Where can {} be found?",
            "Who uses {}?",
            "Which {} is best?",
            "Can you explain {}?",
            "What are the benefits of {}?",
            "How can I improve {}?"
        ]
        
        topic = kwargs.get("topic", self.fake.word())
        template = random.choice(question_types)
        
        return template.format(topic)
    
    def _generate_json(self, **kwargs) -> str:
        """Generate JSON-formatted text."""
        structure = kwargs.get("structure", {
            "id": "uuid",
            "name": "name",
            "email": "email",
            "age": "integer",
            "address": "address",
            "bio": "paragraph"
        })
        
        data = {}
        
        for key, value_type in structure.items():
            if value_type == "uuid":
                data[key] = self.fake.uuid4()
            elif value_type == "name":
                data[key] = self.fake.name()
            elif value_type == "email":
                data[key] = self.fake.email()
            elif value_type == "integer":
                data[key] = random.randint(1, 100)
            elif value_type == "float":
                data[key] = round(random.uniform(0, 100), 2)
            elif value_type == "boolean":
                data[key] = random.choice([True, False])
            elif value_type == "address":
                data[key] = self.fake.address().replace('\n', ', ')
            elif value_type == "paragraph":
                data[key] = self.fake.paragraph()
            elif value_type == "sentence":
                data[key] = self.fake.sentence()
            elif value_type == "word":
                data[key] = self.fake.word()
            elif value_type == "date":
                data[key] = self.fake.date().isoformat()
            else:
                data[key] = str(value_type)
        
        return json.dumps(data, indent=2)
    
    def _generate_from_template(
        self,
        template: str,
        variables: Dict[str, Any]
    ) -> str:
        """Generate text from a template."""
        # Use string.Template for safe substitution
        tmpl = Template(template)
        
        # Ensure all variables are strings
        str_variables = {k: str(v) for k, v in variables.items()}
        
        try:
            return tmpl.safe_substitute(**str_variables)
        except Exception as e:
            logger.error(f"Template substitution failed: {str(e)}")
            raise DataGenerationError(f"Failed to generate from template: {str(e)}")
    
    def generate_dataset(
        self,
        specs: List[Dict[str, Any]],
        output_format: str = "list"
    ) -> Union[List[str], List[Dict[str, str]]]:
        """
        Generate a dataset with mixed text types.
        
        Args:
            specs: List of generation specifications
            output_format: 'list' or 'dict'
            
        Returns:
            Generated dataset
            
        Example specs:
            [
                {"type": "email", "count": 10, "params": {"subject": "Meeting"}},
                {"type": "review", "count": 5, "params": {"rating": 4}},
                {"type": "question", "count": 20, "params": {"topic": "AI"}}
            ]
        """
        dataset = []
        
        for spec in specs:
            text_type = spec.get("type", "paragraph")
            count = spec.get("count", 1)
            params = spec.get("params", {})
            
            texts = self.generate(text_type, count, **params)
            
            if output_format == "dict":
                for text in texts:
                    dataset.append({
                        "type": text_type,
                        "text": text,
                        "metadata": params
                    })
            else:
                dataset.extend(texts)
        
        return dataset
    
    def add_noise(
        self,
        text: str,
        noise_level: float = 0.1,
        noise_types: Optional[List[str]] = None
    ) -> str:
        """
        Add noise to text for robustness testing.
        
        Args:
            text: Original text
            noise_level: Probability of noise (0-1)
            noise_types: Types of noise to add
            
        Returns:
            Noisy text
        """
        if noise_types is None:
            noise_types = ["typo", "case", "punctuation", "whitespace"]
        
        words = text.split()
        noisy_words = []
        
        for word in words:
            if random.random() < noise_level:
                noise_type = random.choice(noise_types)
                
                if noise_type == "typo" and len(word) > 2:
                    # Swap two adjacent characters
                    pos = random.randint(0, len(word) - 2)
                    word = word[:pos] + word[pos+1] + word[pos] + word[pos+2:]
                
                elif noise_type == "case":
                    # Random case change
                    word = ''.join(
                        c.upper() if random.random() < 0.5 else c.lower()
                        for c in word
                    )
                
                elif noise_type == "punctuation":
                    # Add or remove punctuation
                    if word[-1] in '.!?,;:':
                        word = word[:-1]
                    else:
                        word += random.choice('.!?,;:')
                
                elif noise_type == "whitespace":
                    # Add extra spaces
                    word = " " + word + " "
            
            noisy_words.append(word)
        
        return ' '.join(noisy_words)