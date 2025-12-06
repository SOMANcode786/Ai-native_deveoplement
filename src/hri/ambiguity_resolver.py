"""
Ambiguity Resolver for Human-Robot Interaction (HRI) in VLA System

This module handles ambiguous commands by identifying ambiguity sources,
generating clarification questions, and resolving unclear user requests.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import json


class AmbiguityType(Enum):
    """Types of ambiguities in user commands"""
    REFERENCE_AMBIGUITY = "reference_ambiguity"  # Unclear what object is referenced
    SPATIAL_AMBIGUITY = "spatial_ambiguity"      # Unclear location or position
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"    # Unclear timing
    ACTION_AMBIGUITY = "action_ambiguity"        # Unclear what action to perform
    MODALITY_AMBIGUITY = "modality_ambiguity"    # Unclear sensory modality
    SCOPE_AMBIGUITY = "scope_ambiguity"          # Unclear scope of action
    INTENT_AMBIGUITY = "intent_ambiguity"        # Unclear user intent


class ResolutionStrategy(Enum):
    """Strategies for resolving ambiguities"""
    REQUEST_SPECIFIC = "request_specific"         # Ask for specific details
    REQUEST_CONTEXT = "request_context"           # Ask for context
    PRESENT_OPTIONS = "present_options"           # Present possible interpretations
    ASSUME_DEFAULT = "assume_default"             # Use default interpretation
    ASK_FOR_PREFERENCE = "ask_for_preference"     # Ask for user preference
    CONFIRM_INTERPRETATION = "confirm_interpretation"  # Confirm interpretation


@dataclass
class AmbiguitySource:
    """Represents a source of ambiguity in a command"""
    ambiguity_type: AmbiguityType
    text_span: str  # The ambiguous part of the text
    start_pos: int  # Start position in original text
    end_pos: int    # End position in original text
    confidence: float  # Confidence in ambiguity detection
    possible_interpretations: List[str]  # Possible interpretations


@dataclass
class ResolutionCandidate:
    """A candidate resolution for an ambiguity"""
    strategy: ResolutionStrategy
    question: str  # The clarification question to ask
    context_needed: List[str]  # What context is needed
    confidence: float  # Confidence in this resolution approach


class AmbiguityResolver:
    """
    Resolves ambiguities in user commands for the HRI system
    Identifies ambiguous elements and generates appropriate clarification questions
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ambiguity_patterns = self._initialize_ambiguity_patterns()
        self.resolution_templates = self._initialize_resolution_templates()
        self.default_interpretations = self._initialize_default_interpretations()

    def _initialize_ambiguity_patterns(self) -> Dict[AmbiguityType, List[re.Pattern]]:
        """Initialize patterns for detecting different types of ambiguities"""
        return {
            AmbiguityType.REFERENCE_AMBIGUITY: [
                re.compile(r'\b(it|that|this|there|the object|the thing)\b', re.IGNORECASE),
                re.compile(r'\b(there|over there|that one|this one)\b', re.IGNORECASE),
                re.compile(r'\b(some|a|an) \w+\b', re.IGNORECASE)  # "a book" without specifying which
            ],
            AmbiguityType.SPATIAL_AMBIGUITY: [
                re.compile(r'\b(there|over there|nearby|around|somewhere)\b', re.IGNORECASE),
                re.compile(r'\b(place|location|spot|area) \w*\b', re.IGNORECASE),
                re.compile(r'\b(go to|move to|navigate to) \w*\b', re.IGNORECASE)
            ],
            AmbiguityType.TEMPORAL_AMBIGUITY: [
                re.compile(r'\b(now|soon|later|when convenient|asap)\b', re.IGNORECASE),
                re.compile(r'\b(immediately|right away|promptly)\b', re.IGNORECASE)
            ],
            AmbiguityType.ACTION_AMBIGUITY: [
                re.compile(r'\b(do something|handle|deal with|work on) \w*\b', re.IGNORECASE),
                re.compile(r'\b(move|put|place|set) \w+ (somewhere|around|there)\b', re.IGNORECASE)
            ],
            AmbiguityType.SCOPE_AMBIGUITY: [
                re.compile(r'\b(all|every|each|the) \w+ (in|on|at) \w+\b', re.IGNORECASE),
                re.compile(r'\b(clean|organize|arrange) \w+\b', re.IGNORECASE)
            ]
        }

    def _initialize_resolution_templates(self) -> Dict[AmbiguityType, List[str]]:
        """Initialize templates for resolution questions"""
        return {
            AmbiguityType.REFERENCE_AMBIGUITY: [
                "Which {object_type} do you mean?",
                "Could you point to or be more specific about the {object_type}?",
                "There are multiple {object_type}s here. Which one did you mean?"
            ],
            AmbiguityType.SPATIAL_AMBIGUITY: [
                "Where exactly do you mean by '{location}'?",
                "Could you point to the location you want me to go to?",
                "I need a more specific location. Can you be more precise?"
            ],
            AmbiguityType.TEMPORAL_AMBIGUITY: [
                "When exactly would you like me to do this?",
                "Is this urgent, or can it wait?",
                "What's your preferred timeframe for this?"
            ],
            AmbiguityType.ACTION_AMBIGUITY: [
                "What specifically would you like me to do with the {object}?",
                "Could you be more specific about the action?",
                "I'm not sure what you mean by '{action}'. Can you clarify?"
            ],
            AmbiguityType.SCOPE_AMBIGUITY: [
                "How many {objects} did you want me to {action}?",
                "Should I {action} all of them or just some?",
                "What's the scope of this task?"
            ]
        }

    def _initialize_default_interpretations(self) -> Dict[AmbiguityType, str]:
        """Initialize default interpretations for ambiguous elements"""
        return {
            AmbiguityType.REFERENCE_AMBIGUITY: "the closest object of the specified type",
            AmbiguityType.SPATIAL_AMBIGUITY: "the nearest available location",
            AmbiguityType.TEMPORAL_AMBIGUITY: "as soon as possible",
            AmbiguityType.ACTION_AMBIGUITY: "move to a safe position near the object",
            AmbiguityType.SCOPE_AMBIGUITY: "one object or a small subset"
        }

    async def identify_ambiguities(self, command: str) -> List[AmbiguitySource]:
        """
        Identify ambiguities in a user command

        Args:
            command: The user command to analyze

        Returns:
            List of identified ambiguities
        """
        try:
            self.logger.info(f"Identifying ambiguities in command: {command}", extra={
                'command': command
            })

            ambiguities = []

            # Check each ambiguity type
            for ambiguity_type, patterns in self.ambiguity_patterns.items():
                for pattern in patterns:
                    matches = pattern.finditer(command)
                    for match in matches:
                        # Create ambiguity source
                        ambiguity = AmbiguitySource(
                            ambiguity_type=ambiguity_type,
                            text_span=match.group(),
                            start_pos=match.start(),
                            end_pos=match.end(),
                            confidence=0.8,  # Default confidence
                            possible_interpretations=self._generate_possible_interpretations(
                                ambiguity_type, match.group(), command
                            )
                        )
                        ambiguities.append(ambiguity)

            # Apply more sophisticated analysis for context-dependent ambiguities
            context_ambiguities = await self._analyze_context_dependent_ambiguities(command)
            ambiguities.extend(context_ambiguities)

            # Remove duplicates and sort by position
            ambiguities = self._remove_duplicate_ambiguities(ambiguities)
            ambiguities.sort(key=lambda x: x.start_pos)

            self.logger.info(f"Identified {len(ambiguities)} ambiguities", extra={
                'ambiguity_count': len(ambiguities),
                'ambiguity_types': [a.ambiguity_type.value for a in ambiguities]
            })

            return ambiguities

        except Exception as e:
            self.logger.error(f"Error identifying ambiguities: {e}")
            return []

    async def _analyze_context_dependent_ambiguities(self, command: str) -> List[AmbiguitySource]:
        """Analyze ambiguities that depend on context"""
        ambiguities = []

        # Check for pronoun references without clear antecedents
        pronouns = ['it', 'that', 'this', 'they', 'them', 'those']
        for pronoun in pronouns:
            pattern = re.compile(rf'\b{pronoun}\b', re.IGNORECASE)
            matches = pattern.finditer(command)
            for match in matches:
                # Check if there's a clear referent before this pronoun
                text_before = command[:match.start()]
                if not self._has_clear_referent(text_before, pronoun):
                    ambiguity = AmbiguitySource(
                        ambiguity_type=AmbiguityType.REFERENCE_AMBIGUITY,
                        text_span=match.group(),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        confidence=0.7,
                        possible_interpretations=[f"reference to unclear object for '{pronoun}'"]
                    )
                    ambiguities.append(ambiguity)

        return ambiguities

    def _has_clear_referent(self, text_before: str, pronoun: str) -> bool:
        """Check if there's a clear referent for a pronoun in the text before"""
        # Look for potential referents (nouns, noun phrases)
        # This is a simplified check - in practice, you'd use NLP techniques
        potential_referents = re.findall(r'\b(\w+)\b', text_before)
        # Check if any of the last few words could be a referent
        last_words = potential_referents[-5:] if len(potential_referents) >= 5 else potential_referents
        return len(last_words) > 0

    def _generate_possible_interpretations(self, ambiguity_type: AmbiguityType,
                                         text_span: str, full_command: str) -> List[str]:
        """Generate possible interpretations for an ambiguous text span"""
        interpretations = []

        if ambiguity_type == AmbiguityType.REFERENCE_AMBIGUITY:
            # Try to identify possible objects in the environment
            possible_objects = self._extract_possible_objects(full_command)
            interpretations = [f"reference to {obj}" for obj in possible_objects[:3]]  # Limit to 3
        elif ambiguity_type == AmbiguityType.SPATIAL_AMBIGUITY:
            # Identify possible locations
            possible_locations = self._extract_possible_locations(full_command)
            interpretations = [f"location: {loc}" for loc in possible_locations[:3]]
        elif ambiguity_type == AmbiguityType.TEMPORAL_AMBIGUITY:
            interpretations = [
                "immediate execution",
                "execution within 5 minutes",
                "execution when convenient"
            ]
        else:
            # Default interpretations
            interpretations = [f"possible interpretation for '{text_span}'"]

        return interpretations

    def _extract_possible_objects(self, command: str) -> List[str]:
        """Extract possible object references from command"""
        # This is a simplified extraction - in practice, you'd use NLP
        object_patterns = [
            r'(\w+ \w+)',  # color object, e.g., "red cup"
            r'the (\w+)',  # "the cup"
            r'a (\w+)',    # "a cup"
            r'(\w+) object',  # "cup object"
        ]

        objects = []
        for pattern in object_patterns:
            matches = re.findall(pattern, command, re.IGNORECASE)
            objects.extend(matches)

        # Remove duplicates while preserving order
        unique_objects = []
        for obj in objects:
            if obj.lower() not in [u.lower() for u in unique_objects]:
                unique_objects.append(obj)

        return unique_objects

    def _extract_possible_locations(self, command: str) -> List[str]:
        """Extract possible location references from command"""
        location_patterns = [
            r'to (\w+)',
            r'at (\w+)',
            r'in the (\w+)',
            r'(\w+) room',
            r'(\w+) area',
            r'near (\w+)',
            r'by (\w+)'
        ]

        locations = []
        for pattern in location_patterns:
            matches = re.findall(pattern, command, re.IGNORECASE)
            locations.extend(matches)

        # Remove duplicates while preserving order
        unique_locations = []
        for loc in locations:
            if loc.lower() not in [u.lower() for u in unique_locations]:
                unique_locations.append(loc)

        return unique_locations

    def _remove_duplicate_ambiguities(self, ambiguities: List[AmbiguitySource]) -> List[AmbiguitySource]:
        """Remove duplicate ambiguities that overlap or are too similar"""
        if not ambiguities:
            return []

        # Sort by position
        sorted_ambiguities = sorted(ambiguities, key=lambda x: x.start_pos)

        unique_ambiguities = [sorted_ambiguities[0]]

        for current in sorted_ambiguities[1:]:
            last = unique_ambiguities[-1]

            # Check if current ambiguity overlaps with the last one
            if current.start_pos < last.end_pos:
                # If they overlap, keep the one with higher confidence or more specific type
                if current.confidence > last.confidence:
                    unique_ambiguities[-1] = current
            else:
                unique_ambiguities.append(current)

        return unique_ambiguities

    async def generate_resolution_candidates(self, command: str,
                                          ambiguities: List[AmbiguitySource]) -> List[ResolutionCandidate]:
        """
        Generate resolution candidates for identified ambiguities

        Args:
            command: Original user command
            ambiguities: List of identified ambiguities

        Returns:
            List of resolution candidates
        """
        try:
            self.logger.info(f"Generating resolution candidates for {len(ambiguities)} ambiguities", extra={
                'ambiguity_count': len(ambiguities)
            })

            candidates = []

            for ambiguity in ambiguities:
                # Generate candidate for this specific ambiguity
                candidate = await self._generate_single_resolution_candidate(command, ambiguity)
                candidates.append(candidate)

            # If multiple ambiguities exist, consider combined resolution
            if len(ambiguities) > 1:
                combined_candidate = await self._generate_combined_resolution_candidate(command, ambiguities)
                if combined_candidate:
                    candidates.append(combined_candidate)

            self.logger.info(f"Generated {len(candidates)} resolution candidates", extra={
                'candidate_count': len(candidates)
            })

            return candidates

        except Exception as e:
            self.logger.error(f"Error generating resolution candidates: {e}")
            return []

    async def _generate_single_resolution_candidate(self, command: str,
                                                  ambiguity: AmbiguitySource) -> ResolutionCandidate:
        """Generate a resolution candidate for a single ambiguity"""
        # Select the most appropriate strategy based on ambiguity type
        strategy = self._select_resolution_strategy(ambiguity.ambiguity_type)

        # Generate the clarification question
        question = await self._generate_clarification_question(ambiguity, command)

        # Determine context needed
        context_needed = self._determine_context_needed(ambiguity.ambiguity_type)

        # Calculate confidence based on ambiguity type and command context
        confidence = self._calculate_resolution_confidence(ambiguity, command)

        return ResolutionCandidate(
            strategy=strategy,
            question=question,
            context_needed=context_needed,
            confidence=confidence
        )

    async def _generate_combined_resolution_candidate(self, command: str,
                                                    ambiguities: List[AmbiguitySource]) -> Optional[ResolutionCandidate]:
        """Generate a combined resolution for multiple ambiguities"""
        if len(ambiguities) < 2:
            return None

        # Check if ambiguities are related (e.g., multiple reference ambiguities)
        if all(a.ambiguity_type == AmbiguityType.REFERENCE_AMBIGUITY for a in ambiguities):
            # Generate a combined question for multiple references
            question = "I'm not sure what you mean by 'it', 'this', or 'that' in your command. Could you be more specific about which objects you're referring to?"
            return ResolutionCandidate(
                strategy=ResolutionStrategy.REQUEST_SPECIFIC,
                question=question,
                context_needed=["object_references"],
                confidence=0.8
            )

        # For other combinations, return None to use individual candidates
        return None

    def _select_resolution_strategy(self, ambiguity_type: AmbiguityType) -> ResolutionStrategy:
        """Select the most appropriate resolution strategy for an ambiguity type"""
        strategy_mapping = {
            AmbiguityType.REFERENCE_AMBIGUITY: ResolutionStrategy.REQUEST_SPECIFIC,
            AmbiguityType.SPATIAL_AMBIGUITY: ResolutionStrategy.REQUEST_CONTEXT,
            AmbiguityType.TEMPORAL_AMBIGUITY: ResolutionStrategy.REQUEST_CONTEXT,
            AmbiguityType.ACTION_AMBIGUITY: ResolutionStrategy.REQUEST_SPECIFIC,
            AmbiguityType.SCOPE_AMBIGUITY: ResolutionStrategy.ASK_FOR_PREFERENCE,
            AmbiguityType.INTENT_AMBIGUITY: ResolutionStrategy.CONFIRM_INTERPRETATION
        }

        return strategy_mapping.get(ambiguity_type, ResolutionStrategy.REQUEST_CONTEXT)

    async def _generate_clarification_question(self, ambiguity: AmbiguitySource, command: str) -> str:
        """Generate a clarification question for an ambiguity"""
        templates = self.resolution_templates.get(ambiguity.ambiguity_type, [])
        if not templates:
            return f"I didn't understand '{ambiguity.text_span}'. Could you clarify?"

        # Select template based on ambiguity type and context
        template = templates[0]  # Use first template as default

        # Fill in template placeholders
        if ambiguity.ambiguity_type == AmbiguityType.REFERENCE_AMBIGUITY:
            possible_objects = self._extract_possible_objects(command)
            object_type = possible_objects[0] if possible_objects else "object"
            return template.format(object_type=object_type)
        elif ambiguity.ambiguity_type == AmbiguityType.SPATIAL_AMBIGUITY:
            return template.format(location=ambiguity.text_span)
        elif ambiguity.ambiguity_type == AmbiguityType.ACTION_AMBIGUITY:
            return template.format(object="the object", action=ambiguity.text_span)
        elif ambiguity.ambiguity_type == AmbiguityType.SCOPE_AMBIGUITY:
            possible_objects = self._extract_possible_objects(command)
            object_type = possible_objects[0] if possible_objects else "objects"
            return template.format(objects=object_type, action="handle")
        else:
            return template

    def _determine_context_needed(self, ambiguity_type: AmbiguityType) -> List[str]:
        """Determine what context is needed to resolve an ambiguity"""
        context_mapping = {
            AmbiguityType.REFERENCE_AMBIGUITY: ["object_identification", "spatial_context"],
            AmbiguityType.SPATIAL_AMBIGUITY: ["location_data", "environment_map"],
            AmbiguityType.TEMPORAL_AMBIGUITY: ["urgency_level", "time_constraints"],
            AmbiguityType.ACTION_AMBIGUITY: ["action_preferences", "task_details"],
            AmbiguityType.SCOPE_AMBIGUITY: ["task_scope", "quantity_preferences"]
        }

        return context_mapping.get(ambiguity_type, [])

    def _calculate_resolution_confidence(self, ambiguity: AmbiguitySource, command: str) -> float:
        """Calculate confidence in the resolution approach"""
        # Base confidence on ambiguity type
        base_confidence = {
            AmbiguityType.REFERENCE_AMBIGUITY: 0.9,
            AmbiguityType.SPATIAL_AMBIGUITY: 0.85,
            AmbiguityType.TEMPORAL_AMBIGUITY: 0.8,
            AmbiguityType.ACTION_AMBIGUITY: 0.75,
            AmbiguityType.SCOPE_AMBIGUITY: 0.7
        }

        confidence = base_confidence.get(ambiguity.ambiguity_type, 0.5)

        # Adjust based on command complexity
        command_length = len(command.split())
        if command_length > 10:  # Longer commands might have more context
            confidence += 0.05

        return min(1.0, confidence)

    async def resolve_ambiguities(self, command: str, candidates: List[ResolutionCandidate],
                                user_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Resolve ambiguities using the best candidate

        Args:
            command: Original user command
            candidates: List of resolution candidates
            user_context: Additional context about the user

        Returns:
            Tuple of (resolved, response, resolved_context)
        """
        try:
            if not candidates:
                return True, "Command is clear, no ambiguities found", None

            # Select the best candidate based on confidence
            best_candidate = max(candidates, key=lambda x: x.confidence)

            self.logger.info(f"Selected resolution strategy: {best_candidate.strategy.value}", extra={
                'strategy': best_candidate.strategy.value,
                'confidence': best_candidate.confidence
            })

            # If we should ask for clarification, return the question
            if best_candidate.strategy in [ResolutionStrategy.REQUEST_SPECIFIC,
                                         ResolutionStrategy.REQUEST_CONTEXT,
                                         ResolutionStrategy.ASK_FOR_PREFERENCE,
                                         ResolutionStrategy.CONFIRM_INTERPRETATION]:
                return False, best_candidate.question, None

            # If we should assume default, resolve with default interpretation
            elif best_candidate.strategy == ResolutionStrategy.ASSUME_DEFAULT:
                default_interpretation = self.default_interpretations.get(
                    self._get_primary_ambiguity_type(candidates, command),
                    "default interpretation"
                )
                resolved_context = {
                    'assumed_interpretation': default_interpretation,
                    'resolution_strategy': 'default_assumption'
                }
                response = f"Assuming you meant {default_interpretation}. Is that correct?"
                return True, response, resolved_context

            else:
                # For other strategies, return the question
                return False, best_candidate.question, None

        except Exception as e:
            self.logger.error(f"Error resolving ambiguities: {e}")
            return False, "I'm having trouble understanding your request. Could you please rephrase it?", None

    def _get_primary_ambiguity_type(self, candidates: List[ResolutionCandidate], command: str) -> AmbiguityType:
        """Determine the primary ambiguity type in the command"""
        # This is a simplified approach - in practice, you'd analyze the original ambiguities
        command_lower = command.lower()

        if any(word in command_lower for word in ['it', 'that', 'this', 'there']):
            return AmbiguityType.REFERENCE_AMBIGUITY
        elif any(word in command_lower for word in ['there', 'over there', 'nearby', 'around']):
            return AmbiguityType.SPATIAL_AMBIGUITY
        elif any(word in command_lower for word in ['now', 'soon', 'later', 'when']):
            return AmbiguityType.TEMPORAL_AMBIGUITY
        else:
            return AmbiguityType.REFERENCE_AMBIGUITY  # Default

    async def preprocess_command(self, command: str) -> Tuple[str, Dict[str, Any]]:
        """
        Preprocess a command to identify and handle ambiguities

        Args:
            command: User command to preprocess

        Returns:
            Tuple of (disambiguated_command, metadata)
        """
        # Identify ambiguities
        ambiguities = await self.identify_ambiguities(command)

        if not ambiguities:
            # No ambiguities found, return original command
            return command, {
                'has_ambiguities': False,
                'ambiguity_count': 0,
                'resolved': True
            }

        # Generate resolution candidates
        candidates = await self.generate_resolution_candidates(command, ambiguities)

        # Attempt to resolve
        resolved, response, resolved_context = await self.resolve_ambiguities(command, candidates)

        metadata = {
            'has_ambiguities': True,
            'ambiguity_count': len(ambiguities),
            'resolved': resolved,
            'ambiguities_identified': [a.ambiguity_type.value for a in ambiguities],
            'resolution_response': response
        }

        if resolved_context:
            metadata.update(resolved_context)

        # If resolved, return the original command with metadata
        # If not resolved, return the clarification question as the "command"
        result_command = command if resolved else response

        return result_command, metadata


class AmbiguityResolverManager:
    """Manages the ambiguity resolution process in the HRI system"""

    def __init__(self):
        self.resolver = AmbiguityResolver()
        self.logger = logging.getLogger(__name__)
        self.active_resolutions = {}  # Track active resolution sessions

    async def process_command(self, command: str, session_id: str,
                            user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a command for ambiguities and return appropriate response

        Args:
            command: User command to process
            session_id: Unique session identifier
            user_context: Context about the user and environment

        Returns:
            Dictionary with processing results
        """
        try:
            self.logger.info(f"Processing command for session {session_id}: {command}", extra={
                'session_id': session_id,
                'command': command
            })

            # Preprocess the command
            disambiguated_command, metadata = await self.resolver.preprocess_command(command)

            result = {
                'original_command': command,
                'processed_command': disambiguated_command,
                'metadata': metadata,
                'needs_clarification': not metadata.get('resolved', True),
                'session_id': session_id
            }

            # Store in active resolutions if clarification needed
            if result['needs_clarification']:
                self.active_resolutions[session_id] = {
                    'original_command': command,
                    'metadata': metadata,
                    'timestamp': asyncio.get_event_loop().time()
                }

            self.logger.info(f"Command processing result: {'resolved' if metadata.get('resolved', True) else 'needs_clarification'}", extra={
                'session_id': session_id,
                'resolved': metadata.get('resolved', True)
            })

            return result

        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return {
                'original_command': command,
                'processed_command': command,
                'metadata': {'error': str(e)},
                'needs_clarification': True,
                'session_id': session_id,
                'error': str(e)
            }

    async def handle_clarification_response(self, session_id: str, user_response: str) -> Dict[str, Any]:
        """
        Handle user response to a clarification question

        Args:
            session_id: Session identifier
            user_response: User's response to clarification

        Returns:
            Dictionary with resolution results
        """
        try:
            if session_id not in self.active_resolutions:
                return {
                    'error': 'No active resolution for this session',
                    'session_id': session_id
                }

            # Retrieve the original command and context
            active_resolution = self.active_resolutions[session_id]
            original_command = active_resolution['original_command']

            # Combine with original command to create a more specific command
            # This is a simplified approach - in practice, you'd use NLP to integrate the clarification
            resolved_command = f"{original_command} (clarified as: {user_response})"

            # Clean up the active resolution
            del self.active_resolutions[session_id]

            result = {
                'original_command': original_command,
                'resolved_command': resolved_command,
                'user_response': user_response,
                'session_id': session_id,
                'resolution_success': True
            }

            self.logger.info(f"Clarification handled for session {session_id}", extra={
                'session_id': session_id
            })

            return result

        except Exception as e:
            self.logger.error(f"Error handling clarification response: {e}")
            return {
                'error': str(e),
                'session_id': session_id
            }

    def get_active_resolutions(self) -> Dict[str, Any]:
        """Get information about active resolution sessions"""
        return self.active_resolutions


# Example usage and testing
async def test_ambiguity_resolver():
    """Test the ambiguity resolver system"""
    print("Testing Ambiguity Resolver System")
    print("=" * 40)

    resolver = AmbiguityResolver()
    manager = AmbiguityResolverManager()

    # Test commands with various ambiguities
    test_commands = [
        "Move it to there",  # Reference and spatial ambiguity
        "Clean the table",   # Could be spatially ambiguous if there are multiple tables
        "Pick up that object",  # Reference ambiguity
        "Go to the kitchen when you can",  # Temporal ambiguity
        "Handle all the items",  # Scope ambiguity
        "Move the red cup to somewhere safe",  # Spatial ambiguity
        "Do something with this",  # Action ambiguity
    ]

    print("\nTesting ambiguity detection:")
    for i, command in enumerate(test_commands, 1):
        print(f"\n{i}. Command: '{command}'")

        # Identify ambiguities
        ambiguities = await resolver.identify_ambiguities(command)
        print(f"   Detected ambiguities: {len(ambiguities)}")

        for j, amb in enumerate(ambiguities, 1):
            print(f"   {j}. {amb.ambiguity_type.value}: '{amb.text_span}'")
            if amb.possible_interpretations:
                print(f"      Possible interpretations: {amb.possible_interpretations[:2]}")  # Show first 2

        # Generate resolution candidates
        candidates = await resolver.generate_resolution_candidates(command, ambiguities)
        print(f"   Resolution candidates: {len(candidates)}")

        if candidates:
            best_candidate = candidates[0]
            print(f"   Best strategy: {best_candidate.strategy.value}")
            print(f"   Question: {best_candidate.question}")

    # Test the full resolution process
    print(f"\nTesting full resolution process:")
    session_id = "test_session_1"
    result = await manager.process_command("Move it to there", session_id)
    print(f"   Original: Move it to there")
    print(f"   Needs clarification: {result['needs_clarification']}")
    print(f"   Response: {result['metadata'].get('resolution_response', 'N/A')}")

    # Simulate user response
    if result['needs_clarification']:
        clarification_result = await manager.handle_clarification_response(
            session_id, "Move the red cup to the table"
        )
        print(f"   After clarification: {clarification_result.get('resolved_command', 'N/A')}")

    print(f"\nAmbiguity resolver system test completed!")


if __name__ == "__main__":
    asyncio.run(test_ambiguity_resolver())