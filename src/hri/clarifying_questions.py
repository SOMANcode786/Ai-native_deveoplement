"""
Clarifying Question Generation for Human-Robot Interaction (HRI) in VLA System

This module generates appropriate clarifying questions when the robot doesn't
understand user commands or needs more information to execute tasks successfully.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class QuestionCategory(Enum):
    """Categories of clarifying questions"""
    REFERENCE = "reference"           # What object/location are you referring to?
    SPECIFICATION = "specification"    # More specific details needed
    PREFERENCE = "preference"         # User preferences
    ALTERNATIVE = "alternative"       # Alternative options
    VERIFICATION = "verification"     # Confirming understanding
    CAPABILITY = "capability"         # Checking robot capabilities


class QuestionType(Enum):
    """Types of clarifying questions"""
    YES_NO = "yes_no"           # Simple yes/no question
    CHOICE = "choice"           # Multiple choice question
    OPEN_ENDED = "open_ended"    # Open-ended question
    RANKING = "ranking"         # Ask to rank options


@dataclass
class ClarifyingQuestion:
    """Represents a clarifying question"""
    question_text: str
    category: QuestionCategory
    question_type: QuestionType
    options: Optional[List[str]] = None  # For choice/ranking questions
    required_follow_up: bool = False    # Whether answer requires more questions
    confidence: float = 1.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ClarifyingQuestionGenerator:
    """
    Generates clarifying questions for ambiguous or incomplete user commands
    Helps the robot gather necessary information to execute tasks successfully
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.question_templates = self._initialize_question_templates()
        self.patterns = self._initialize_patterns()
        self.response_processors = self._initialize_response_processors()

    def _initialize_question_templates(self) -> Dict[QuestionCategory, Dict[QuestionType, List[str]]]:
        """Initialize templates for different types of clarifying questions"""
        return {
            QuestionCategory.REFERENCE: {
                QuestionType.OPEN_ENDED: [
                    "Which {object_type} do you mean?",
                    "Could you point to or be more specific about the {object_type}?",
                    "I see multiple {object_type}s here. Which one did you want me to {action}?",
                    "Can you describe the {object_type} you're referring to more specifically?"
                ],
                QuestionType.CHOICE: [
                    "Did you mean the {option1} or the {option2} {object_type}?",
                    "Are you referring to {option1} or {option2}?",
                    "I see {option1} and {option2}. Which one did you want?"
                ]
            },
            QuestionCategory.SPECIFICATION: {
                QuestionType.OPEN_ENDED: [
                    "How {attribute} should the {action} be?",
                    "Can you be more specific about {aspect}?",
                    "What exactly did you mean by {vague_term}?",
                    "Could you provide more details about {aspect}?"
                ],
                QuestionType.CHOICE: [
                    "Did you want me to {action1} or {action2}?",
                    "Would you prefer {option1} or {option2}?",
                    "Should I {action1} first or {action2} first?"
                ]
            },
            QuestionCategory.PREFERENCE: {
                QuestionType.YES_NO: [
                    "Would you prefer {option1} over {option2}?",
                    "Is {option1} acceptable?",
                    "Do you have a preference for {aspect}?"
                ],
                QuestionType.CHOICE: [
                    "What is your preference: {option1}, {option2}, or {option3}?",
                    "Which option do you prefer: {option1} or {option2}?",
                    "How would you like me to {action}: {option1}, {option2}, or {option3}?"
                ]
            },
            QuestionCategory.ALTERNATIVE: {
                QuestionType.CHOICE: [
                    "I can't do exactly that, but I can {action1}, {action2}, or {action3}. Which would you prefer?",
                    "Instead of {original_action}, I can {alternative1} or {alternative2}. What would you prefer?",
                    "I'm unable to {original_task}. Would you like me to {alternative1} or {alternative2} instead?"
                ]
            },
            QuestionCategory.VERIFICATION: {
                QuestionType.YES_NO: [
                    "Just to confirm, you want me to {action_description}. Is that correct?",
                    "So you'd like me to {action_description}? Did I understand correctly?",
                    "Let me make sure: you want {action_description}. Right?"
                ]
            },
            QuestionCategory.CAPABILITY: {
                QuestionType.YES_NO: [
                    "I can {capability1} or {capability2}. Which would be more helpful?",
                    "I'm able to {action1} but not {action2}. Would {action1} work for you?",
                    "I can {capability} if that's what you need. Is that acceptable?"
                ]
            }
        }

    def _initialize_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize patterns for detecting different types of ambiguities"""
        return {
            'vague_references': re.compile(r'\b(it|that|this|there|the object|the thing|something)\b', re.IGNORECASE),
            'vague_locations': re.compile(r'\b(there|over there|nearby|around|somewhere|here|that area)\b', re.IGNORECASE),
            'vague_actions': re.compile(r'\b(do something|handle|deal with|work on|take care of|figure out)\b', re.IGNORECASE),
            'quantifiers': re.compile(r'\b(all|every|each|some|many|few|a lot of|most)\b', re.IGNORECASE),
            'temporal_vagueness': re.compile(r'\b(now|soon|later|when convenient|asap|immediately|right away)\b', re.IGNORECASE),
            'comparatives': re.compile(r'\b(better|worse|more|less|larger|smaller|faster|slower)\b', re.IGNORECASE),
            'ambiguous_pronouns': re.compile(r'\b(it|they|them|those|these)\b', re.IGNORECASE)
        }

    def _initialize_response_processors(self) -> Dict[QuestionType, callable]:
        """Initialize processors for different types of responses"""
        return {
            QuestionType.YES_NO: self._process_yes_no_response,
            QuestionType.CHOICE: self._process_choice_response,
            QuestionType.OPEN_ENDED: self._process_open_ended_response,
            QuestionType.RANKING: self._process_ranking_response
        }

    def generate_clarifying_questions(self, command: str, context: Optional[Dict[str, Any]] = None) -> List[ClarifyingQuestion]:
        """
        Generate clarifying questions for an ambiguous command

        Args:
            command: The user command that needs clarification
            context: Additional context about the situation

        Returns:
            List of clarifying questions
        """
        try:
            self.logger.info(f"Generating clarifying questions for: {command}", extra={
                'command': command
            })

            questions = []

            # Detect different types of ambiguities and generate appropriate questions
            questions.extend(self._generate_reference_questions(command, context))
            questions.extend(self._generate_specification_questions(command, context))
            questions.extend(self._generate_preference_questions(command, context))
            questions.extend(self._generate_alternative_questions(command, context))
            questions.extend(self._generate_verification_questions(command, context))
            questions.extend(self._generate_capability_questions(command, context))

            # Filter and rank questions
            filtered_questions = self._filter_questions(questions, command, context)

            # Sort by confidence (highest first)
            sorted_questions = sorted(filtered_questions, key=lambda q: q.confidence, reverse=True)

            self.logger.info(f"Generated {len(sorted_questions)} clarifying questions", extra={
                'question_count': len(sorted_questions),
                'categories': list(set(q.category.value for q in sorted_questions))
            })

            return sorted_questions

        except Exception as e:
            self.logger.error(f"Error generating clarifying questions: {e}")
            return []

    def _generate_reference_questions(self, command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Generate questions about unclear references"""
        questions = []

        # Check for vague references
        vague_refs = self.patterns['vague_references'].findall(command)
        vague_locs = self.patterns['vague_locations'].findall(command)
        ambiguous_pronouns = self.patterns['ambiguous_pronouns'].findall(command)

        all_vague_refs = vague_refs + vague_locs + ambiguous_pronouns

        if all_vague_refs:
            # Extract possible objects from context or command
            possible_objects = self._extract_possible_objects(command, context)
            possible_locations = self._extract_possible_locations(command, context)

            if possible_objects:
                # Generate specific reference questions
                for obj_type in set(possible_objects):
                    question_text = self._fill_template(
                        self.question_templates[QuestionCategory.REFERENCE][QuestionType.OPEN_ENDED][0],
                        {'object_type': obj_type, 'action': self._extract_action(command)}
                    )
                    questions.append(ClarifyingQuestion(
                        question_text=question_text,
                        category=QuestionCategory.REFERENCE,
                        question_type=QuestionType.OPEN_ENDED,
                        confidence=0.9
                    ))

            if len(possible_objects) >= 2:
                # Generate choice question between objects
                obj1, obj2 = possible_objects[:2]
                question_text = self._fill_template(
                    self.question_templates[QuestionCategory.REFERENCE][QuestionType.CHOICE][0],
                    {'option1': obj1, 'option2': obj2, 'object_type': 'object'}
                )
                questions.append(ClarifyingQuestion(
                    question_text=question_text,
                    category=QuestionCategory.REFERENCE,
                    question_type=QuestionType.CHOICE,
                    options=[obj1, obj2],
                    confidence=0.8
                ))

        return questions

    def _generate_specification_questions(self, command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Generate questions asking for more specific details"""
        questions = []

        # Look for vague terms and generate specification questions
        if any(word in command.lower() for word in ['something', 'thing', 'stuff', 'object']):
            question_text = self._fill_template(
                self.question_templates[QuestionCategory.SPECIFICATION][QuestionType.OPEN_ENDED][1],
                {'aspect': 'what specific object you mean'}
            )
            questions.append(ClarifyingQuestion(
                question_text=question_text,
                category=QuestionCategory.SPECIFICATION,
                question_type=QuestionType.OPEN_ENDED,
                confidence=0.8
            ))

        # Check for temporal vagueness
        if self.patterns['temporal_vagueness'].search(command):
            question_text = "When exactly would you like me to do this?"
            questions.append(ClarifyingQuestion(
                question_text=question_text,
                category=QuestionCategory.SPECIFICATION,
                question_type=QuestionType.OPEN_ENDED,
                confidence=0.7
            ))

        # Check for vague quantities
        if self.patterns['quantifiers'].search(command):
            question_text = self._fill_template(
                self.question_templates[QuestionCategory.SPECIFICATION][QuestionType.OPEN_ENDED][1],
                {'aspect': 'how many or which specific items'}
            )
            questions.append(ClarifyingQuestion(
                question_text=question_text,
                category=QuestionCategory.SPECIFICATION,
                question_type=QuestionType.OPEN_ENDED,
                confidence=0.7
            ))

        return questions

    def _generate_preference_questions(self, command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Generate questions about user preferences"""
        questions = []

        # If context provides options, ask about preferences
        if context and 'available_options' in context:
            options = context['available_options']
            if len(options) >= 2:
                question_text = self._fill_template(
                    self.question_templates[QuestionCategory.PREFERENCE][QuestionType.CHOICE][0],
                    {
                        'option1': options[0],
                        'option2': options[1],
                        'option3': options[2] if len(options) > 2 else options[1]
                    }
                )
                questions.append(ClarifyingQuestion(
                    question_text=question_text,
                    category=QuestionCategory.PREFERENCE,
                    question_type=QuestionType.CHOICE,
                    options=options,
                    confidence=0.8
                ))

        return questions

    def _generate_alternative_questions(self, command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Generate questions offering alternative approaches"""
        questions = []

        # If the command seems impossible or difficult, suggest alternatives
        if any(phrase in command.lower() for phrase in ['impossible', 'difficult', 'too hard', "can't do"]):
            alternatives = self._suggest_alternatives(command)
            if len(alternatives) >= 2:
                question_text = self._fill_template(
                    self.question_templates[QuestionCategory.ALTERNATIVE][QuestionType.CHOICE][0],
                    {
                        'action1': alternatives[0],
                        'action2': alternatives[1],
                        'action3': alternatives[2] if len(alternatives) > 2 else alternatives[1]
                    }
                )
                questions.append(ClarifyingQuestion(
                    question_text=question_text,
                    category=QuestionCategory.ALTERNATIVE,
                    question_type=QuestionType.CHOICE,
                    options=alternatives,
                    confidence=0.8
                ))

        return questions

    def _generate_verification_questions(self, command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Generate questions to verify understanding"""
        questions = []

        # If command is complex or has multiple steps, verify understanding
        action_description = self._describe_action(command)
        if action_description and len(action_description.split()) > 5:  # Complex command
            question_text = self._fill_template(
                self.question_templates[QuestionCategory.VERIFICATION][QuestionType.YES_NO][0],
                {'action_description': action_description}
            )
            questions.append(ClarifyingQuestion(
                question_text=question_text,
                category=QuestionCategory.VERIFICATION,
                question_type=QuestionType.YES_NO,
                confidence=0.7
            ))

        return questions

    def _generate_capability_questions(self, command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Generate questions about robot capabilities"""
        questions = []

        # Check if command requests capabilities we might not have
        if context and 'robot_capabilities' in context:
            requested_action = self._extract_action(command)
            available_capabilities = context['robot_capabilities']

            if requested_action and requested_action not in available_capabilities:
                capability_alternatives = self._find_capability_alternatives(requested_action, available_capabilities)
                if capability_alternatives:
                    question_text = self._fill_template(
                        self.question_templates[QuestionCategory.CAPABILITY][QuestionType.YES_NO][0],
                        {
                            'capability1': capability_alternatives[0],
                            'capability2': capability_alternatives[1] if len(capability_alternatives) > 1 else 'other tasks'
                        }
                    )
                    questions.append(ClarifyingQuestion(
                        question_text=question_text,
                        category=QuestionCategory.CAPABILITY,
                        question_type=QuestionType.YES_NO,
                        options=capability_alternatives,
                        confidence=0.8
                    ))

        return questions

    def _filter_questions(self, questions: List[ClarifyingQuestion], command: str, context: Optional[Dict[str, Any]]) -> List[ClarifyingQuestion]:
        """Filter and refine the list of questions"""
        if not questions:
            return []

        # Remove duplicate questions
        unique_questions = []
        seen_texts = set()

        for question in questions:
            if question.question_text not in seen_texts:
                unique_questions.append(question)
                seen_texts.add(question.question_text)

        # Adjust confidence based on relevance to command
        for question in unique_questions:
            question.confidence *= self._calculate_relevance_score(question.question_text, command)

        # Only return questions with reasonable confidence
        filtered = [q for q in unique_questions if q.confidence > 0.3]

        return filtered

    def _fill_template(self, template: str, params: Dict[str, str]) -> str:
        """Fill in template parameters"""
        try:
            return template.format(**params)
        except KeyError:
            # If formatting fails, return template as-is
            return template

    def _extract_possible_objects(self, command: str, context: Optional[Dict[str, Any]]) -> List[str]:
        """Extract possible object references from command and context"""
        objects = []

        # From command
        # Look for color + object patterns: "red cup", "blue box"
        color_obj_pattern = re.compile(r'(\w+)\s+(\w+)', re.IGNORECASE)
        matches = color_obj_pattern.findall(command)
        for match in matches:
            if match[0] in ['red', 'blue', 'green', 'yellow', 'black', 'white', 'brown', 'orange']:  # colors
                objects.append(f"{match[0]} {match[1]}")

        # From context if available
        if context and 'environment_objects' in context:
            objects.extend(context['environment_objects'])

        # Add common object types
        obj_types = ['cup', 'book', 'box', 'bottle', 'pen', 'phone', 'computer']
        for obj_type in obj_types:
            if obj_type in command.lower():
                objects.append(obj_type)

        return list(set(objects))  # Remove duplicates

    def _extract_possible_locations(self, command: str, context: Optional[Dict[str, Any]]) -> List[str]:
        """Extract possible location references"""
        locations = []

        # From command
        location_pattern = re.compile(r'(?:to|at|in|on)\s+(\w+)', re.IGNORECASE)
        matches = location_pattern.findall(command)
        locations.extend(matches)

        # Common locations
        common_locs = ['kitchen', 'living room', 'bedroom', 'office', 'table', 'counter', 'shelf', 'cabinet']
        for loc in common_locs:
            if loc in command.lower():
                locations.append(loc)

        # From context if available
        if context and 'known_locations' in context:
            locations.extend(context['known_locations'])

        return list(set(locations))

    def _extract_action(self, command: str) -> str:
        """Extract the main action from a command"""
        # Simple action extraction - in practice, you'd use NLP
        action_words = ['move', 'pick', 'place', 'grasp', 'navigate', 'go', 'take', 'put', 'clean', 'organize']
        for word in action_words:
            if word in command.lower():
                return word
        return 'perform action'

    def _describe_action(self, command: str) -> str:
        """Create a description of the action in the command"""
        # This would be more sophisticated in practice
        return command[:50] + "..." if len(command) > 50 else command

    def _suggest_alternatives(self, command: str) -> List[str]:
        """Suggest alternative actions"""
        action = self._extract_action(command)

        alternatives = {
            'move': ['navigate to', 'go near', 'approach'],
            'pick': ['identify', 'point to', 'locate'],
            'place': ['hold', 'carry', 'transport'],
            'grasp': ['touch', 'approach', 'identify'],
            'navigate': ['move toward', 'go in direction of'],
            'clean': ['organize', 'arrange', 'tidy']
        }

        return alternatives.get(action, [f'do something similar to {action}', f'attempt {action} differently'])

    def _find_capability_alternatives(self, requested_action: str, available_capabilities: List[str]) -> List[str]:
        """Find alternative capabilities similar to requested action"""
        # This is a simplified version - in practice, you'd have a more sophisticated mapping
        action_synonyms = {
            'grasp': ['manipulate', 'handle', 'move'],
            'navigate': ['move', 'go', 'travel'],
            'speak': ['communicate', 'talk', 'interact'],
            'see': ['detect', 'recognize', 'identify']
        }

        alternatives = []
        for syn_action, syn_list in action_synonyms.items():
            if requested_action in syn_list or syn_action == requested_action:
                alternatives.extend([cap for cap in available_capabilities if cap in syn_list])

        return alternatives[:3]  # Return top 3

    def _calculate_relevance_score(self, question: str, command: str) -> float:
        """Calculate how relevant a question is to the command"""
        score = 0.5  # Base score

        # Boost score if question contains key terms from command
        command_lower = command.lower()
        question_lower = question.lower()

        # Count matching words
        command_words = set(command_lower.split())
        question_words = set(question_lower.split())

        matching_words = command_words.intersection(question_words)
        if matching_words:
            score += len(matching_words) * 0.1

        # Boost for specific question types
        if '?' in question:
            score += 0.1
        if any(wh_word in question_lower for wh_word in ['which', 'what', 'where', 'how']):
            score += 0.1

        return min(1.0, score)

    def select_best_question(self, questions: List[ClarifyingQuestion], context: Optional[Dict[str, Any]] = None) -> Optional[ClarifyingQuestion]:
        """
        Select the most appropriate clarifying question

        Args:
            questions: List of generated clarifying questions
            context: Additional context

        Returns:
            The best clarifying question or None if no questions generated
        """
        if not questions:
            return None

        # Sort by confidence and category priority
        category_priority = {
            QuestionCategory.REFERENCE: 1,
            QuestionCategory.SPECIFICATION: 2,
            QuestionCategory.CAPABILITY: 3,
            QuestionCategory.PREFERENCE: 4,
            QuestionCategory.VERIFICATION: 5,
            QuestionCategory.ALTERNATIVE: 6
        }

        def question_sort_key(q):
            return (category_priority.get(q.category, 10), q.confidence)

        sorted_questions = sorted(questions, key=question_sort_key, reverse=True)
        return sorted_questions[0]

    def process_user_response(self, question: ClarifyingQuestion, user_response: str) -> Dict[str, Any]:
        """
        Process a user's response to a clarifying question

        Args:
            question: The question that was asked
            user_response: The user's response

        Returns:
            Dictionary with processed response information
        """
        try:
            processor = self.response_processors.get(question.question_type)
            if processor:
                return processor(question, user_response)
            else:
                return {
                    'interpreted_response': user_response,
                    'confidence': 0.5,
                    'needs_followup': False
                }

        except Exception as e:
            self.logger.error(f"Error processing user response: {e}")
            return {
                'error': str(e),
                'needs_clarification': True
            }

    def _process_yes_no_response(self, question: ClarifyingQuestion, response: str) -> Dict[str, Any]:
        """Process a yes/no response"""
        response_lower = response.lower()
        if any(word in response_lower for word in ['yes', 'yeah', 'yep', 'sure', 'correct', 'right', 'ok', 'okay']):
            return {
                'interpreted_response': True,
                'confidence': 0.9,
                'needs_followup': False
            }
        elif any(word in response_lower for word in ['no', 'nope', 'not', 'wrong', 'incorrect']):
            return {
                'interpreted_response': False,
                'confidence': 0.9,
                'needs_followup': False
            }
        else:
            return {
                'interpreted_response': response,
                'confidence': 0.3,
                'needs_followup': True,
                'reason': 'Unclear yes/no response'
            }

    def _process_choice_response(self, question: ClarifyingQuestion, response: str) -> Dict[str, Any]:
        """Process a choice response"""
        if not question.options:
            return {
                'interpreted_response': response,
                'confidence': 0.5,
                'needs_followup': True
            }

        response_lower = response.lower()
        for option in question.options:
            if option.lower() in response_lower or response_lower in option.lower():
                return {
                    'interpreted_response': option,
                    'confidence': 0.8,
                    'needs_followup': False
                }

        # If no exact match, try partial matching
        for option in question.options:
            option_words = set(option.lower().split())
            response_words = set(response_lower.split())
            if len(option_words.intersection(response_words)) > 0:
                return {
                    'interpreted_response': option,
                    'confidence': 0.6,
                    'needs_followup': False
                }

        return {
            'interpreted_response': response,
            'confidence': 0.2,
            'needs_followup': True,
            'reason': 'Response does not match any of the options'
        }

    def _process_open_ended_response(self, question: ClarifyingQuestion, response: str) -> Dict[str, Any]:
        """Process an open-ended response"""
        return {
            'interpreted_response': response,
            'confidence': 0.7,
            'needs_followup': False,
            'raw_response': response
        }

    def _process_ranking_response(self, question: ClarifyingQuestion, response: str) -> Dict[str, Any]:
        """Process a ranking response"""
        # This is a simplified implementation
        # In practice, you'd parse rankings like "1st: option A, 2nd: option B"
        return {
            'interpreted_response': response,
            'confidence': 0.5,
            'needs_followup': False
        }


class ClarifyingQuestionManager:
    """Manages the clarifying question process in the HRI system"""

    def __init__(self):
        self.generator = ClarifyingQuestionGenerator()
        self.logger = logging.getLogger(__name__)
        self.active_sessions = {}  # Track active clarification sessions

    async def initiate_clarification(self, command: str, context: Optional[Dict[str, Any]] = None,
                                   session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiate a clarification process for an ambiguous command

        Args:
            command: The ambiguous user command
            context: Additional context about the situation
            session_id: Session identifier

        Returns:
            Dictionary with clarification information
        """
        try:
            self.logger.info(f"Initiating clarification for command: {command}", extra={
                'command': command,
                'session_id': session_id
            })

            # Generate clarifying questions
            questions = self.generator.generate_clarifying_questions(command, context)

            if not questions:
                return {
                    'command': command,
                    'needs_clarification': False,
                    'message': 'Command is clear',
                    'session_id': session_id
                }

            # Select the best question
            best_question = self.generator.select_best_question(questions, context)

            result = {
                'command': command,
                'needs_clarification': True,
                'clarifying_question': best_question.question_text if best_question else "I need more information.",
                'question_category': best_question.category.value if best_question else None,
                'question_type': best_question.question_type.value if best_question else None,
                'options': best_question.options if best_question else None,
                'question_confidence': best_question.confidence if best_question else 0.0,
                'all_questions': [q.question_text for q in questions[:3]],  # Top 3 questions
                'session_id': session_id
            }

            # Store session if ID provided
            if session_id and best_question:
                self.active_sessions[session_id] = {
                    'original_command': command,
                    'clarifying_question': best_question,
                    'context': context,
                    'timestamp': datetime.now()
                }

            self.logger.info(f"Clarification initiated with question: {best_question.question_text if best_question else 'None'}", extra={
                'session_id': session_id,
                'question_count': len(questions)
            })

            return result

        except Exception as e:
            self.logger.error(f"Error initiating clarification: {e}")
            return {
                'command': command,
                'error': str(e),
                'needs_clarification': True,
                'clarifying_question': "I'm having trouble understanding. Could you please rephrase that?",
                'session_id': session_id
            }

    async def process_response(self, session_id: str, user_response: str) -> Dict[str, Any]:
        """
        Process a user's response to a clarifying question

        Args:
            session_id: Session identifier
            user_response: User's response to the clarifying question

        Returns:
            Dictionary with response processing results
        """
        try:
            if session_id not in self.active_sessions:
                return {
                    'error': 'No active clarification session',
                    'session_id': session_id
                }

            session_data = self.active_sessions[session_id]
            clarifying_question = session_data['clarifying_question']

            # Process the user's response
            processed_response = self.generator.process_user_response(clarifying_question, user_response)

            result = {
                'session_id': session_id,
                'original_command': session_data['original_command'],
                'user_response': user_response,
                'processed_response': processed_response,
                'needs_more_clarification': processed_response.get('needs_followup', False),
                'interpreted_meaning': processed_response.get('interpreted_response'),
                'confidence': processed_response.get('confidence', 0.5)
            }

            # If no more clarification needed, remove session
            if not processed_response.get('needs_followup', False):
                del self.active_sessions[session_id]

            self.logger.info(f"Processed clarification response", extra={
                'session_id': session_id,
                'confidence': processed_response.get('confidence', 0.5)
            })

            return result

        except Exception as e:
            self.logger.error(f"Error processing response: {e}")
            return {
                'error': str(e),
                'session_id': session_id
            }

    def get_active_sessions(self) -> Dict[str, Any]:
        """Get information about active clarification sessions"""
        return {
            session_id: {
                'original_command': data['original_command'],
                'question': data['clarifying_question'].question_text,
                'category': data['clarifying_question'].category.value,
                'timestamp': data['timestamp'].isoformat()
            }
            for session_id, data in self.active_sessions.items()
        }


# Example usage and testing
async def test_clarifying_questions():
    """Test the clarifying question generation system"""
    print("Testing Clarifying Question Generation System")
    print("=" * 55)

    generator = ClarifyingQuestionGenerator()
    manager = ClarifyingQuestionManager()

    # Test commands that need clarification
    test_commands = [
        "Move it to there",
        "Pick up the thing",
        "Clean everything",
        "Go to the room",
        "Do something with this",
        "Handle all the items in the area",
        "Move the object near the thing",
        "Organize stuff in the space"
    ]

    print("\nTesting clarifying question generation:")
    for i, command in enumerate(test_commands, 1):
        print(f"\n{i}. Command: '{command}'")

        # Generate questions
        questions = generator.generate_clarifying_questions(command)
        print(f"   Generated {len(questions)} questions:")

        for j, question in enumerate(questions[:3], 1):  # Show top 3
            print(f"   {j}. [{question.category.value}] {question.question_text}")
            print(f"      Type: {question.question_type.value}, Confidence: {question.confidence:.2f}")

        # Select best question
        best_question = generator.select_best_question(questions)
        if best_question:
            print(f"   Best question: {best_question.question_text}")

    # Test the full clarification process
    print(f"\nTesting full clarification process:")
    session_id = "test_session_1"
    result = await manager.initiate_clarification("Move it to there", session_id=session_id)

    print(f"   Original command: {result['command']}")
    print(f"   Needs clarification: {result['needs_clarification']}")
    if result['needs_clarification']:
        print(f"   Clarifying question: {result['clarifying_question']}")
        print(f"   Question type: {result['question_type']}")
        print(f"   Confidence: {result['question_confidence']:.2f}")

    # Simulate user response
    if result['needs_clarification']:
        response_result = await manager.process_response(session_id, "Move the red cup to the table")
        print(f"   User response: Move the red cup to the table")
        print(f"   Interpreted meaning: {response_result['interpreted_meaning']}")
        print(f"   Confidence: {response_result['confidence']:.2f}")
        print(f"   Needs more clarification: {response_result['needs_more_clarification']}")

    # Show active sessions
    print(f"\nActive clarification sessions: {len(manager.get_active_sessions())}")

    print(f"\nClarifying question generation test completed!")


if __name__ == "__main__":
    asyncio.run(test_clarifying_questions())