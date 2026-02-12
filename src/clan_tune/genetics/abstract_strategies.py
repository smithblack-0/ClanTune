"""
Abstract strategy classes for genome evolution.

Strategies provide decision logic for genome evolution - which alleles to mutate,
which parents to select, how to combine values. Abstract classes define the hook-based
pattern and delegation contracts; concrete implementations (in mutation_strategies.py,
ancestry_strategies.py, crossbreeding_strategies.py) provide the algorithms.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Optional, Callable
from uuid import UUID

from .genome import Genome
from .alleles import AbstractAllele, CanMutateFilter, CanCrossbreedFilter


class AbstractStrategy(ABC):
    """
    Root strategy class providing optional setup infrastructure.

    Provides setup hooks that concrete strategies can override to inject metadata
    alleles for metalearning. The default implementation is a no-op. Child strategies
    (ancestry, crossbreeding, mutation) extend this to add their specific application
    logic.

    Stateless.
    """

    def setup_genome(self, genome: Genome) -> Genome:
        """
        Optional setup hook that transforms allele tree before training begins.

        Orchestrates setup by walking alleles and calling handle_setup on each.
        Enables metalearning by injecting metadata alleles that can evolve alongside
        primary hyperparameters.

        Args:
            genome: Genome to set up

        Returns:
            Genome with metadata alleles injected (if handle_setup overridden)
        """
        # Walk alleles, calling handle_setup on each
        # This is a direct walk over the allele dictionary, not recursive tree walk
        new_alleles = {}
        for key, allele in genome.alleles.items():
            new_alleles[key] = self.handle_setup(allele)

        # Return genome with transformed alleles
        return genome.with_alleles(alleles=new_alleles)

    def handle_setup(self, allele: AbstractAllele) -> AbstractAllele:
        """
        Hook for injecting metadata alleles during setup.

        Default implementation returns allele unchanged. Concrete strategies override
        to inject metadata via allele.with_metadata(**updates). Never modifies
        allele.value - setup injects only metadata.

        Args:
            allele: Allele to potentially augment with metadata

        Returns:
            Allele with metadata injected (or unchanged if no metalearning)
        """
        return allele

    @abstractmethod
    def apply_strategy(self, *args, **kwargs) -> Any:
        """
        Abstract method that subclasses must implement.

        Defines how a genome or population of genomes is transformed. Subclasses
        narrow the signature and implement their specific strategy logic.
        """
        ...


class AbstractAncestryStrategy(AbstractStrategy):
    """
    Parent selection strategy using declare-interpret paradigm.

    Declares which genomes become parents and their contribution probabilities via
    ancestry structure. Downstream systems (crossbreeding strategies, model state
    reconstruction) interpret that declaration. This separation enables mixing
    selection strategies with synthesis strategies independently.

    Ancestry format: List[Tuple[float, UUID]] in rank order where:
    - List length equals population size
    - Index corresponds to population rank
    - Tuple (probability, uuid) declares contribution strength
    - Probability 0.0 means excluded from reproduction
    - Sum of probabilities typically equals 1.0 (not enforced)

    Stateless. Concrete subclasses define selection parameters.
    """

    def apply_strategy(
        self, my_genome: Genome, population: List[Genome]
    ) -> List[Tuple[float, UUID]]:
        """
        Select parents and declare contribution probabilities.

        Orchestrates ancestry selection by validating inputs, dispatching to
        select_ancestry hook, and validating output. This is declaration, not
        synthesis - returns ancestry structure, not a genome.

        Args:
            my_genome: Genome being evolved (must be in population)
            population: All genomes in rank order (fitness must be set)

        Returns:
            Ancestry declaring parent contributions in rank order

        Raises:
            ValueError: If fitness not set, my_genome not in population,
                       or ancestry length doesn't match population size
        """
        # Validation 1: Fitness must be set on all genomes
        for genome in population:
            if genome.fitness is None:
                raise ValueError("All genomes must have fitness set before selection")

        # Validation 2: my_genome must be in population
        if my_genome not in population:
            raise ValueError("my_genome must be in population")

        # Dispatch to concrete hook
        ancestry = self.select_ancestry(my_genome, population)

        # Validation 3: Ancestry length must match population size
        if len(ancestry) != len(population):
            raise ValueError(
                f"Ancestry length ({len(ancestry)}) must equal population size ({len(population)})"
            )

        return ancestry

    @abstractmethod
    def select_ancestry(
        self, my_genome: Genome, population: List[Genome]
    ) -> List[Tuple[float, UUID]]:
        """
        Abstract hook for parent selection logic.

        Concrete strategies implement fitness-based selection algorithms:
        tournament selection, fitness-weighted sampling, diversity-based filtering, etc.

        Args:
            my_genome: Genome being evolved
            population: All genomes in rank order (lower fitness is better)

        Returns:
            Ancestry as [(probability, uuid), ...] in rank order where:
            - List length equals population size
            - Index corresponds to population rank
            - Probability 0.0 means no contribution
            - Sum typically equals 1.0 (not enforced)
        """
        ...


class AbstractCrossbreedingStrategy(AbstractStrategy):
    """
    Allele synthesis strategy interpreting ancestry to create offspring genomes.

    While AbstractAncestryStrategy declares which parents contribute,
    AbstractCrossbreedingStrategy interprets how ancestry plays out for individual
    alleles - weighted combinations, dominant selection, stochastic sampling, etc.

    Delegates to genome.synthesize_new_alleles for tree traversal, implementing only
    the allele-level synthesis logic via handle_crossbreeding hook.

    Stateless. Concrete subclasses define crossbreeding parameters.
    """

    def apply_strategy(
        self,
        my_genome: Genome,
        population: List[Genome],
        ancestry: List[Tuple[float, UUID]],
    ) -> Genome:
        """
        Synthesize offspring genome by crossbreeding parent alleles.

        Orchestrates crossbreeding by delegating to genome.synthesize_new_alleles,
        passing self.handle_crossbreeding as handler with ancestry injected via kwargs
        dict. Only processes alleles with can_crossbreed=True recursively.

        Args:
            my_genome: Template genome (must be in population)
            population: All parent genomes
            ancestry: Parent contribution probabilities from ancestry strategy

        Returns:
            New genome with synthesized alleles
        """
        # Delegate to genome utility for tree traversal, injecting ancestry via kwargs
        return my_genome.synthesize_new_alleles(
            population,
            self.handle_crossbreeding,
            predicate=CanCrossbreedFilter(True),
            kwargs={"ancestry": ancestry},
        )

    @abstractmethod
    def handle_crossbreeding(
        self,
        template: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        """
        Abstract hook for allele-level crossbreeding logic.

        Concrete strategies interpret ancestry to synthesize new allele values:
        weighted average, dominant parent selection, stochastic sampling, etc.

        Args:
            template: Allele from my_genome (flattened metadata contains raw values)
            allele_population: Alleles from population (flattened, same position as template)
            ancestry: Parent contribution probabilities

        Returns:
            New allele synthesized from parent values, typically via
            template.with_value(new_value)
        """
        ...


class AbstractMutationStrategy(AbstractStrategy):
    """
    Genome mutation strategy for introducing variation.

    Modifies allele values to drive exploration of the hyperparameter space. Receives
    population and ancestry context to enable population-aware mutations (e.g.,
    differential evolution using other genomes' values). Simple mutations ignore
    these parameters.

    Delegates to genome.update_alleles for tree traversal, implementing only the
    allele-level mutation logic via handle_mutating hook.

    Stateless. Concrete subclasses define mutation parameters.
    """

    def apply_strategy(
        self,
        genome: Genome,
        population: List[Genome],
        ancestry: List[Tuple[float, UUID]],
    ) -> Genome:
        """
        Mutate genome alleles to introduce variation.

        Orchestrates mutation by delegating to genome.update_alleles, passing
        self.handle_mutating as handler with population and ancestry injected via
        kwargs dict. Only processes alleles with can_mutate=True recursively.

        Args:
            genome: Genome to mutate
            population: All genomes (for population-aware mutations)
            ancestry: Parent contributions (for adaptive mutations)

        Returns:
            New genome with mutated alleles
        """

        # Adapt synthesize new genome. We need synthesize genome to allow
        # operation with a allele that is not in population. We do this by
        # inserting it and then removing it before usage
        population = population.copy()
        population.append(genome)

        def handle_adapter(allele: AbstractAllele,
                           allele_population: List[AbstractAllele],
                           ancestry: List[Tuple[float, UUID]],
                           )->AbstractAllele:
            allele_population = allele_population.copy()
            allele_population.pop()
            return self.handle_mutating(allele, allele_population, ancestry)


        # Delegate to genome utility, injecting population and ancestry via kwargs
        return genome.synthesize_new_alleles(
            population,
            handle_adapter,
            predicate=CanMutateFilter(True),
            kwargs={"ancestry": ancestry},
        )

    @abstractmethod
    def handle_mutating(
        self,
        allele: AbstractAllele,
        population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        """
        Abstract hook for allele-level mutation logic.

        Concrete strategies implement mutation algorithms: Gaussian noise, Cauchy
        perturbations, differential evolution, uniform sampling, etc. Population-aware
        strategies use population/ancestry parameters; simple mutations ignore them.

        Args:
            allele: Allele to mutate (flattened metadata contains raw values)
            population: Alleles in the population at this location.
            ancestry: Parent contributions (for adaptive mutations)

        Returns:
            New allele with mutated value, typically via allele.with_value(new_value)
        """
        ...


class StrategyOrchestrator:
    """
    Coordinates genome evolution by composing ancestry, crossbreeding, and mutation.

    Packages three strategies together and ensures proper sequencing: ancestry
    selection → crossbreeding → mutation → ancestry recording. Convenience utility
    for testing and simple use cases; higher-level orchestration (Individual, State)
    handles population management and model state reconstruction.

    Concrete class. Stateful (holds strategy instances as dependencies).
    """

    def __init__(
        self,
        ancestry_strategy: AbstractAncestryStrategy,
        crossbreeding_strategy: AbstractCrossbreedingStrategy,
        mutation_strategy: AbstractMutationStrategy,
    ):
        """
        Construct orchestrator with strategy dependencies.

        Args:
            ancestry_strategy: Strategy for parent selection
            crossbreeding_strategy: Strategy for allele synthesis
            mutation_strategy: Strategy for allele mutation
        """
        self.ancestry_strategy = ancestry_strategy
        self.crossbreeding_strategy = crossbreeding_strategy
        self.mutation_strategy = mutation_strategy

    def setup_genome(self, genome: Genome) -> Genome:
        """
        Chain setup calls through all three strategies.

        Calls ancestry_strategy.setup_genome, then crossbreeding_strategy.setup_genome,
        then mutation_strategy.setup_genome in sequence. Each strategy gets a chance
        to inject its metadata alleles; they operate independently without coordination.

        Args:
            genome: Genome to set up

        Returns:
            Genome with all metalearning metadata injected
        """
        genome = self.ancestry_strategy.setup_genome(genome)
        genome = self.crossbreeding_strategy.setup_genome(genome)
        genome = self.mutation_strategy.setup_genome(genome)
        return genome

    def __call__(self, my_genome: Genome, population: List[Genome]) -> Genome:
        """
        Execute genome evolution cycle.

        Orchestrates: ancestry selection → crossbreeding → mutation → ancestry recording.
        Returns offspring genome ready for fitness evaluation.

        Args:
            my_genome: Genome being evolved (must be in population)
            population: All genomes (fitness must be set)

        Returns:
            Offspring genome (new UUID, no fitness, parents set to ancestry)
        """
        # Step 1: Select parents and declare contributions
        ancestry = self.ancestry_strategy.apply_strategy(my_genome, population)

        # Step 2: Crossbreed parent alleles to create offspring
        offspring = self.crossbreeding_strategy.apply_strategy(
            my_genome, population, ancestry
        )

        # Step 3: Mutate offspring alleles
        mutated_offspring = self.mutation_strategy.apply_strategy(
            offspring, population, ancestry
        )

        # Step 4: Attach ancestry - orchestrator owns ancestry expression on final offspring
        return mutated_offspring.with_ancestry(ancestry)
