Feature: Bounded experimental decision partner
  An owner supplies a finite decision model and explicit experiment likelihoods.
  COMPASS-C inspects decision value and returns an advisory proposal, never runs it.

  Scenario: A costly signal can reverse a decision
    Given a sourced two-scenario model whose current expected-value winner is defer
    And an experiment with explicitly supplied signal likelihoods, cost and duration
    When the owner requests proposals within a cost and duration budget
    Then each outcome shows its probability, posterior, conditional winners and reversal
    And the proposal separates no-test value, perfect information, sample information and net value
    And only a positive-net-value experiment within both bounds is proposed

  Scenario: Uncertainty alone does not justify an experiment
    Given different scenarios whose uncertainty never changes the preferred action
    When an experiment reveals the scenario
    Then its information has zero decision value
    And no experiment is proposed

  Scenario: Impossible and tiny-probability outcomes remain inspectable
    Given an experiment with an outcome of zero probability and one of tiny positive probability
    When proposals are inspected
    Then the impossible outcome has no invented posterior
    And every possible outcome retains exact probabilities and conditional winners

  Scenario: Observed results revise a model without erasing provenance
    Given a model, a supplied experiment and an explicitly sourced dated observation
    When the owner requests a belief update
    Then Bayes' rule produces a reusable revised model and an inspectable update record
    And the original model, observation, likelihoods, provenance and assumptions are preserved
    And no input is mutated and no record is automatically written

  Scenario: An observation contradicts the supplied model
    Given an outcome with zero probability under the supplied model
    When that outcome is reported as observed
    Then the update fails with an impossible-observation error
    And the prior remains unchanged

  Scenario: Bounds and unsupported models are rejected explicitly
    Given missing probabilities, malformed likelihoods or unsupported dimensions
    When a proposal or update is requested
    Then COMPASS-C returns a stable invalid-input error
    And it does not invent missing probabilities or source evidence
