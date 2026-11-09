# Structure mapping, schema induction, hierarchical Bayesian overhypotheses, and far transfer (June–Nov 2026, with marked precursors)

Scope note for the report writer. Window asked for: June 2026 – November 2026 (today 2026-11-09). Anything earlier is tagged **[PRECURSOR]**. Every item below was opened (arXiv abstract page or publisher page) unless marked **[snippet only]**, in which case only the search snippet or metadata could be read (paywall/redirect/PDF-binary) and the claim should be treated as unverified at the sentence level. Target system for the "judgement" lines: a symbolic per-action effect predictor (Bayesian averaging over small explanation sets, six tool-call worlds, no LLM at runtime) whose three attempts to carry explanation-form priors across worlds (prior on explanation size and cell kind; per outcome kind; whole action pattern with input roles) all failed to beat an empty mind, although action forms overlap across worlds (17/37 identical full forms, seed 1).

Headline: in the June–Nov 2026 window I found **no** paper that shows relational/structural alignment making a new domain faster **without an LLM and without domain-specific hand-coding**. The only 2026 "transfer to a new environment by role/relational mapping" results (RoleWorld, ASPECT, YARN) all use an LLM as the mapper or abstractor. The one purely symbolic 2026 structure-mapping paper (SMTB, Sept 2026) is an engine-speed result, not a transfer result. Hierarchical-Bayesian-overhypothesis work in the window is thin: one negative result (Cacioli, Apr 2026, precursor) and one task-diversity RL result (Seth et al., May/Oct 2026) that is the closest thing to a "when does learning-to-learn help vs hurt" finding. Human far-transfer evidence in 2026 remains mostly null for cognitive training and mixed for variability.

---

## (a) Computational structure mapping / analogy for transfer to new domains (Gentner lineage, relational nets, ARC-style few-shot adaptation with and without LLMs)

### Takeaway
2026 structure-mapping work is either (i) a faster symbolic mapper evaluated on mapping quality, not on downstream transfer (SMTB), or (ii) LLM-plus-mapper hybrids where the LLM supplies the abstraction level and the mapper supplies alignment (YARN, ASPECT, RoleWorld). Non-LLM ARC results exist but at low absolute scores (VSA 3–6% eval; CompressARC 20% eval, precursor) and none measure cross-task transfer of learned structure; the ARC-AGI-3 interactive line explicitly starts each game from a clean slate.

### Cited Findings

**In-window (June–Nov 2026)**

- **SMTB: Fast Structure-Mapping with Tight Bounds** — Daniel Weitekamp & Christopher MacLellan, arXiv:2609.25508, submitted 22 Sep 2026 (cs.AI). Symbolic structure-mapping algorithm (part of the Cognitive Rule Engine, Python over C++). Measured: speed and mapping quality vs SME v4 on 5,845 domain pairs from the SME corpus. Numbers: 5–15x faster than SME; ~50% better at finding mappings in large nested domains. Given to system: relationally connected elements (arbitrary relational graphs or nested predicate logic); it "maximizes relational connectivity without privileging higher-order relations." No downstream transfer or learning-speed test. — [arXiv 2609.25508](https://arxiv.org/abs/2609.25508)
  *Judgement:* Directly usable as a drop-in, LLM-free mapper between two worlds' action-effect relational graphs; it tells you *how* to align specific action pairs cheaply, but gives no evidence that aligned pairs speed up a new world.

- **ARCANA: A Reflective Multi-Agent Program Synthesis Framework for ARC-AGI-2 Reasoning** — Kunbo Zhang, Lei Fu, Zeyu Wang, Zijing Liu, Kejian Tong, arXiv:2607.09059, submitted 10 Jul 2026. Perception agent builds object-centric scene graphs from raw grids; latent program policy proposes DSL programs; symbolic executor verifies against demos; reflective agent converts failures into feedback; learned meta-controller schedules agents. Score not stated on abstract page (search snippet claimed 32.5% semi-private, unverified). LLM use at runtime not stated on abstract page. — [arXiv 2607.09059](https://arxiv.org/abs/2607.09059)
  *Judgement:* Per-task search-and-verify loop, no cross-task carry; irrelevant to carrying priors across worlds.

- **RoleWorld: Knowledge Transfer in World Modeling with Functional Role Abstractions** — Boyuan Xiao, Pu Wang, Ji Feng, Yao-Xiang Ding, arXiv:2610.13172, submitted 9 Oct 2026. Symbolic world model for LLM agents: reusable *role prototypes* + environment-specific parameter values describe how objects behave in interactions. A teacher LLM extracts role prototypes, executable transition rules, and a guiding skill from source-environment trajectories; in a new environment the actor LLM keeps transition rules fixed and refines role assignments and parameters online (no weight updates), testing role hypotheses when uncertainty affects a decision. Measured: generalization on the MARS benchmark including environments with "significantly altered" object behaviour. Transfer numbers: not in abstract. — [arXiv 2610.13172](https://arxiv.org/abs/2610.13172)
  *Judgement:* The most relevant 2026 architecture: what is carried is *not* a prior over rule form but (role prototype + fixed transition rule) with per-world free parameters and per-object role assignment inferred by test. That is exactly "relational mapping of specific action pairs" rather than "prior over explanation form." LLM does the extraction, so the mechanism, not the implementation, transfers to the target system.

- **Enhancing Structural Mapping with LLM-derived Abstractions for Analogical Reasoning in Narratives (YARN)** — M. Khojasteh, Y. Jiang, S. De Giorgis, F. van Harmelen, F. Ilievski, arXiv:2603.29997, submitted 31 Mar 2026 **[PRECURSOR, Mar 2026]**. LLM decomposes narratives into units and abstracts them at four levels; a structural mapping component aligns across stories. Finding: "abstractions consistently improve model performance," competitive or better than end-to-end LLM; LLMs alone struggle when structural mapping is required. Numbers not on abstract page. — [arXiv 2603.29997](https://arxiv.org/abs/2603.29997)
  *Judgement:* Supports the split "abstraction level is the hard part; alignment is cheap." Target system has no LLM to pick abstraction level, so this says the bottleneck for it is choosing the right abstraction of an action, not the mapper.

- **Transformer See, Transformer Do: Copying as an Intermediate Step in Learning Analogical Reasoning** — P. Hellwig, W. Zuidema, C. E. Stevenson, M. Lewis, arXiv:2604.06501, v1 7 Apr 2026, v2 19 Aug 2026, accepted COLM 2026. Meta-Learning for Compositionality on letter-string analogies; a 3-layer encoder-decoder "on par with frontier models"; generalization to new alphabets improves with more heterogeneous training; MLC gives some generalization to compositions of trained transformations "but not to completely novel transformations." — [arXiv 2604.06501](https://arxiv.org/abs/2604.06501)
  *Judgement:* Evidence that learned analogical transfer reaches recombinations of seen relations but not new relations; for the target system, carrying action forms only helps where the new world's action is a recombination of seen ones.

- **Auto-Relational Reasoning** — I. Konstantoulas, D. Tsimas, P. Peppas, K. Sgarbas, arXiv:2604.26507, submitted 29 Apr 2026 (submitted to JAIR). Framework for automatic reasoning over object relations with neural nets; 98.03% on IQ-style problems "without any prior knowledge of the problem"; no OOD/cross-task numbers. — [arXiv 2604.26507](https://arxiv.org/abs/2604.26507)
  *Judgement:* No transfer measurement; not useful.

- **From numerical proportions to analogical proportions between probabilities** — Henri Prade & Gilles Richard, arXiv:2606.23029, submitted 22 Jun 2026. Defines "a:b::c:d" over probability values and distributions (arithmetic/geometric proportion); experiments on whether profiles whose attribute-distributions form a proportion have classes forming a proportion; results not in abstract. — [arXiv 2606.23029](https://arxiv.org/abs/2606.23029)
  *Judgement:* Marginal; a formal tool for analogical inference over *distributions* (which is what Bayesian averaging produces) but no transfer evidence.

- **Task Scarcity and Label Leakage in Relational Transfer Learning** — F. Galuppo Azevedo, C. Lima Loures, D. Oliveira Correa, arXiv:2603.29914, 31 Mar 2026, ICLR 2026 DATA-FM workshop **[PRECURSOR, Mar 2026]**. Relational foundation models: too few prediction targets per database let representations learn task-specific shortcuts ("label leakage") that degrade transfer "even within the same schema"; gradient projection removing label-predictive directions improves within-dataset transfer by +0.145 AUROC on RelBench. Conclusion: limited *task diversity*, not limited data, constrains transfer. — [arXiv 2603.29914](https://arxiv.org/abs/2603.29914)
  *Judgement:* A mechanistic reason transfer can fail: what was learned on source tasks encodes source-task shortcuts. For the target system, an explanation-form prior fit on 12 sessions in one world may be a shortcut on that world's outcome labels rather than a form regularity.

- **Executable World Models for ARC-AGI-3 in the Era of Coding Agents** — Sergey Rodionov, arXiv:2605.05138, v1 6 May 2026, v2 6 Jun 2026, accepted AGI-2026. Coding agent (GPT-5.5 / GPT-5.4) keeps an executable Python world model, verifies it against past observations, simplifies it (MDL proxy), plans through it. 25 public games: GPT-5.5 fully solved 15, mean per-game RHAE 58.12%; GPT-5.4 solved 8, 41.29%. Same agent/prompts across all games, no game-specific code. **No reuse across games**: each playthrough is a fresh instance with clean workspace. — [arXiv 2605.05138](https://arxiv.org/abs/2605.05138)
  *Judgement:* Confirms that the strongest 2026 interactive-world results are per-world; nobody has shown carrying a world model across ARC-AGI-3 games helps.

- **Graph-Based Exploration for ARC-AGI-3 Interactive Reasoning Tasks** — E. Rudakov, J. Shock, B. U. Cowley, arXiv:2512.24156, 30 Dec 2025, AAAI 2026 workshop **[PRECURSOR]**. Training-free: segments frames into components, ranks actions by visual salience, keeps a directed graph of explored state-action transitions, prioritizes shortest path to untested pairs. Median 30/52 levels across six games on the ARC-AGI-3 Preview; 3rd on private leaderboard; "substantially" outperforms LLM agents (no numbers in abstract). No cross-game transfer. — [arXiv 2512.24156](https://arxiv.org/abs/2512.24156)
  *Judgement:* LLM-free exploration of a tool-call-like world; no carry across worlds, so it is a baseline design for "empty mind explores well," which is consistent with the target system's finding that an empty mind is hard to beat.

- **ARC-AGI Without Pretraining (CompressARC)** — Isaac Liao & Albert Gu, arXiv:2512.06104, 5 Dec 2025 **[PRECURSOR]**. 76K-parameter model, no pretraining, trained only on the target puzzle with the answer removed, minimizing description length; ~20% of ARC-AGI-1 evaluation. — [arXiv 2512.06104](https://arxiv.org/abs/2512.06104)
  *Judgement:* Shows an MDL prior with zero carried knowledge is competitive; another "empty mind + compression" result.

- **Vector Symbolic Algebras for the Abstraction and Reasoning Corpus** — Isaac Joffe & Chris Eliasmith, arXiv:2511.08747, 11 Nov 2025 **[PRECURSOR]**; a Nature-portfolio version (s44335-026-00100-5) exists in 2026 but was behind a redirect **[snippet only]**. Object-centric program synthesis with VSAs; 10.8% ARC-AGI-1-Train, 3.0% Eval (v1); 94.5% Sort-of-ARC, 83.1% 1D-ARC. Later versions (2026 NeSy conference) 13.5% / 3.5%; ensemble 21.0% / 6.3% [snippet only]. — [arXiv 2511.08747](https://arxiv.org/abs/2511.08747v1); [Nature page](https://www.nature.com/articles/s44335-026-00100-5)
  *Judgement:* LLM-free, structured, but per-task; no transfer across tasks measured.

- **The ARC of Progress towards AGI: A Living Survey** — S. Vahdati, A. Aioanei, H. Suresh, J. Lehmann, arXiv:2603.13372, 9 Mar 2026 **[PRECURSOR]**. 82 approaches; performance drops 2–3x from ARC-AGI-1 to -2 across all paradigms (program synthesis, neuro-symbolic, neural); tops 93.0% ARC-AGI-1, 68.8% ARC-AGI-2, 13% ARC-AGI-3; 2025 Prize winners at 24% on ARC-AGI-2 needed hundreds of thousands of synthetic examples; test-time adaptation is "critical," compositional reasoning and interactive learning "unsolved." — [arXiv 2603.13372](https://arxiv.org/abs/2603.13372)

- **Relational Transformer: Toward Zero-Shot Foundation Models for Relational Data** — R. Ranjan et al. (Guestrin, Leskovec), arXiv:2510.06377, v1 7 Oct 2025, v3 2 Mar 2026, ICLR 2026 **[PRECURSOR]**. Pretrained on diverse relational DBs; zero-shot on unseen RelBench tasks averages 93% of fully-supervised AUROC (22M params) vs 84% for a 27B LLM. Given: task table prompts, table/column metadata, cell values. — [arXiv 2510.06377](https://arxiv.org/abs/2510.06377)
  *Judgement:* Zero-shot relational transfer works when schema *semantics* (column names) are given; the target system gives field names in observations, so the analogue is "column-name-level" alignment of action argument roles.

- **ASPECT: Analogical Semantic Policy Execution via Language Conditioned Transfer** — A. S. Palattuparambil, T. G. Karimpanal, S. Rana, arXiv:2604.08355, 9–10 Apr 2026 **[PRECURSOR]**. RL zero-shot transfer: LLM remaps the target observation description onto the source task; text-conditioned VAE imagines a source-compatible state; original policy reused. Numbers not in abstract. — [arXiv 2604.08355](https://arxiv.org/abs/2604.08355)

- **Data Analogies Enable Efficient Cross-Embodiment Transfer** — J. Yang, C. Finn, D. Sadigh, arXiv:2603.06450, 6/20 Mar 2026 **[PRECURSOR]**. Paired demonstrations aligning scenes/tasks/trajectories across embodiments beat unstructured diversity for morphology changes; real-world +22.5% average over large unpaired datasets by changing data composition only. — [arXiv 2603.06450](https://arxiv.org/abs/2603.06450)
  *Judgement:* Explicit *paired* correspondences (analogies) transfer where generic diversity does not; argues for carrying aligned action pairs, not marginal statistics.

### Inferences
- Every 2026 system that successfully reused structure in a *new* environment carried (relation, role, fixed rule) triples with free per-world parameters and inferred the role assignment online (RoleWorld), or carried explicit paired correspondences (Data Analogies). None carried a distribution over *rule shape*.
- Non-LLM ARC and ARC-AGI-3 systems in 2026 are strongest when they carry nothing and compress or explore well; this is the same shape as the target system's "empty mind is hard to beat."

### Gaps
- No ARC Prize 2026 technical report found as of 2026-11-09 (the 2025 report, arXiv:2601.10904, Jan 2026, and the ARC-AGI-3 technical report PDF, dated 22 Apr 2026 per search snippet, were not readable as text) **[snippet only]**.
- SMTB, RoleWorld, ASPECT, YARN abstract pages give no transfer-size numbers; full PDFs were not opened.
- CogSci 2026 proceedings: program PDF too large to fetch; only session "T.16.3 Using Analogical Comparison to Reveal the Structure of the Count" surfaced [snippet only]; no 2026 proceedings paper on analogy-driven transfer could be verified.

---

## (b) Schema induction by comparing multiple cases (Gick & Holyoak lineage) implemented in machines

### Takeaway
I found **no June–Nov 2026 machine paper** implementing Gick-and-Holyoak-style schema induction from comparison of multiple cases. The 2026 items closest in spirit are library learning in humans (Zhao et al., Mar 2026, precursor) and the LLM-guided Bayesian "mental programs" model (Piriyakulkij et al., Sep 2026), neither of which compares cases to induce a schema.

### Cited Findings
- **Induction and Inquiry via Probabilistic Reasoning over Language and Code** — W. T. Piriyakulkij, S. Acquaviva, C. Langenfeld, J. Tenenbaum, K. Ellis, arXiv:2609.01815, 1 Sep 2026. Knowledge as "mental programs that combine natural language with source code," inferred sequentially by LLM-guided Bayesian learning; reproduces anchoring and garden-pathing in human inductive learning and active inquiry; pure LLMs and classic Bayesian models "either fail, don't match human behaviour, or are too costly." No numbers in abstract; no hierarchical/learning-to-learn or cross-domain transfer claim. — [arXiv 2609.01815](https://arxiv.org/abs/2609.01815)
  *Judgement:* Confirms Tenenbaum-lab direction is per-task sequential Bayesian program induction with an LLM proposer; it does not address carrying priors across tasks, so it neither helps nor contradicts the target system's result.
- **Online library learning in human visual puzzle solving** — P. Zhao, E. Sansone, M. Kryven, B. Zhao, arXiv:2603.23244, 24 Mar 2026 **[PRECURSOR]**. Humans define and reuse "helpers" capturing repeating structure; early abundant helpers, later selective; helpers let participants solve otherwise-impossible puzzles; decision times and operation counts rise with search-space size estimated by a library-learning program-induction model; raw program length predicts failure but not effort. — [arXiv 2603.23244](https://arxiv.org/abs/2603.23244)
  *Judgement:* Reuse unit is a concrete sub-program (helper), induced from repetition *within* a growing task stream, not a prior over form; suggests carrying reusable sub-explanations rather than form statistics.
- **Few-Shot Learning of Visual Compositional Concepts through Probabilistic Schema Induction (PSI)** — Lee et al., CogSci 2025, arXiv:2505.09859 **[PRECURSOR, 2025]**. Deep-learning analogical mapping over structured representations of a handful of examples to form a schema; beats deep-learning baselines (numbers not re-verified here). — [arXiv 2505.09859](https://arxiv.org/pdf/2505.09859)
- **Mix & Gentner (2026), perspective in *Discover Education* 5:288, DOI 10.1007/s44217-026-01248-9** — steps teachers can take to raise relational reasoning via structure-mapping; PDF fetched as binary, body not read **[snippet only]**. — [PDF](https://groups.psych.northwestern.edu/gentner/papers/Mix&Gentner%202026.pdf)
- Classic basis (not 2026): comparing two analogs yields a schema whose quality predicts transfer (Gick & Holyoak 1983) — [Deep Blue record](https://deepblue.lib.umich.edu/items/196ea13e-fb69-4a74-a6f9-864c81aed465)

### Inferences
- Machine schema induction remains per-domain few-shot (PSI) or human-modelling (library learning). The missing experiment for the target system is: align *two worlds'* action-effect cases by SMTB-style mapping and keep only the intersection as the schema, rather than a marginal prior.

### Gaps
- No 2026 machine implementation of multi-case schema induction with cross-domain transfer numbers was found; searched arXiv-indexed results, CogSci, Semantic-Scholar-style snippets.

---

## (c) Hierarchical Bayesian / overhypothesis models of learning-to-learn (Kemp–Perfors–Tenenbaum lineage) and 2026 results on when they help vs hurt

### Takeaway
No June–Nov 2026 paper directly extends Kemp–Perfors–Tenenbaum. The best 2026 "help vs hurt" evidence is from RL task diversity (Seth, Gershman, Kleiman-Weiner, Carvalho et al., May/Oct 2026): diversity yields systematic transfer to new distributions but causes a plateau in continual learning; and from Bayesian transfer learning (TRADER, Total Risk Prior, 2026 revisions) formalizing negative transfer from mis-aligned sources. One 2026 negative result shows distributional learners reach perfect exemplar retrieval but chance (50–52%) on the second-order overhypothesis (Cacioli, Apr 2026).

### Cited Findings
- **Task diversity produces systematic transfer but inhibits continual reinforcement learning** — P. Seth, N. Shah, I. Sinha, K. Jha, S. J. Gershman, M. Kleiman-Weiner, W. Carvalho, arXiv:2606.00880, v1 30 May 2026, v2 6 Oct 2026. New GPU continual-RL domain "Banyan" with three parametric axes (map layout, objects, hierarchical sub-goal structure). Increasing task diversity gives "systematic transfer": agents begin a new task distribution near their previous performance even when optimal policy structure changes; but too much diversity makes learners plateau on new tasks while still improving on old ones; plateau appears across continual-learning algorithms, memory architectures, sizes, and in Kinetix. No numbers in abstract. — [arXiv 2606.00880](https://arxiv.org/abs/2606.00880)
  *Judgement:* The clearest 2026 "when learning-to-learn helps vs hurts": a carried prior helps the *starting point* in a new distribution and can hurt *continued* learning. For the target system, note it measured carry at k=3/6/12/25 with no gain even at the start, so it is below the regime where this paper's benefit appears, or the carried statistic is not the one that transfers.
- **Exemplar Retrieval Without Overhypothesis Induction** — Jon-Paul Cacioli, arXiv:2604.05243, 6 Apr 2026 **[PRECURSOR, Apr 2026]**. 3.4M–25.6M autoregressive transformers, 8 synthetic conditions, 120 pre-registered runs, 1,040-item wug battery: 100% first-order exemplar retrieval, 50–52% (chance, confirmed by equivalence test) on second-order generalization to novel nouns (shape bias); feature-swap diagnostic shows frame-to-feature templates rather than noun→domain→feature abstraction. — [arXiv 2604.05243](https://arxiv.org/abs/2604.05243)
  *Judgement:* A clean case where a learner that stores and retrieves specifics perfectly does **not** induce the overhypothesis; by analogy, the target system's "marginal never-met-value statistic adds nothing" is the expected outcome unless the carried unit is a structured second-order abstraction.
- **Bayesian Transfer Learning for Enhanced Estimation and Inference (TRADER)** — arXiv:2412.02986, revised 2026 **[PRECURSOR; snippet only]**. Shrinkage prior yielding faster posterior contraction when sources align with target "while preventing negative transfer from heterogeneous sources." — [arXiv 2412.02986](https://arxiv.org/html/2412.02986)
- **Formal Bayesian Transfer Learning via the Total Risk Prior** — arXiv:2507.23768, revised 2026 **[PRECURSOR; snippet only]**. Binary inclusion indicators let each source dataset be excluded; argues two-stage methods cannot retroactively remove sources causing negative transfer. — [arXiv 2507.23768](https://arxiv.org/html/2507.23768)
- **Bayesian Meta-Learning with Expert Feedback for Task-Shift Adaptation through Causal Embeddings** — arXiv:2602.19788, Feb 2026 **[PRECURSOR; snippet only]**: reduced negative transfer on OOD tasks via causal embeddings. — [paperswithcode mirror](https://paperswithcode.co/paper/2602.19788)
- **Transfer learning for nonparametric Bayesian networks** — arXiv:2604.01021, Apr 2026 **[PRECURSOR; snippet only]**: defines metrics to address negative transfer. — [arXiv 2604.01021](https://arxiv.org/abs/2604.01021)
- **Separable Pathways for Causal Reasoning: Architectural Scaffolding Enables Hypothesis-Space Restructuring in LLM Agents** — J. Alderete, S. Benthall, C. Xu, J. Xing, arXiv:2604.20039, 21 Apr 2026 **[PRECURSOR]**. Blicket-detector extension; 1,085 trials; "context graphs" (typed state machines) account for 94% of the accuracy gain; "dynamic behaviours" detect regime change and expand the hypothesis space at runtime. No transfer measured. — [arXiv 2604.20039](https://arxiv.org/abs/2604.20039)
- Foundational **[PRECURSOR]**: Kemp, Perfors & Tenenbaum (2007), overhypotheses as learned priors (shape bias, feature variability, ontological kinds). — [PDF](https://www.mit.edu/~jbt/temp/KempPerforsTenenbaum.pdf); Kosoy et al. 2022 causal overhypotheses, tabular Q-learning fails held-out scenarios — [arXiv 2206.08353](https://arxiv.org/pdf/2206.08353); PAC-Bayes meta-learning: larger hyper-prior misspecification → larger gain, but meta-learning can produce negative transfer — [JMLR](https://www.jmlr.org/papers/volume24/22-1254/22-1254.pdf)

### Inferences
- The 2026 Bayesian-transfer literature treats negative transfer as the default risk and solves it by *source-selection* (inclusion indicators, shrinkage) rather than by better priors on form. The target system's empty-mind baseline being unbeaten is consistent with sources (other worlds) being heterogeneous at the level of explanation form, even though 17/37 action forms coincide.
- Overhypothesis learning in KPT 2007 works because the *same feature dimension* (shape) recurs across categories. Explanation form (size, cell kind, outcome kind) is not a dimension that recurs with the same meaning across tool-call worlds; action-argument roles are.

### Gaps
- No 2026 paper found that tests hierarchical-Bayesian overhypothesis transfer in symbolic action-effect prediction; searched arXiv/PsyArXiv-indexed results for "overhypothesis" 2026.
- Seth et al. numbers (how much transfer, at what diversity the plateau starts) are in the PDF, not read.

---

## (d) Human and animal far-transfer and developmental evidence 2026 (does far transfer exist, under what conditions)

### Takeaway
2026 meta-analytic evidence for far transfer from cognitive training is null (sustained far transfer g = 0.02, 95% CI −0.26 to 0.29); 2026 variability studies split, with one direct intervention finding variability slows learning and does **not** improve generalization; developmental work keeps finding that structured comparison (not exposure to a model alone) drives children's relational learning, and that analogical transfer tracks world knowledge and working memory more than age. No animal far-transfer paper from 2026 was found.

### Cited Findings
- **Cognitive transfer and durability of computerised cognitive training in older adults with MCI: systematic review and meta-analysis of RCTs** — H. Luo, L. Deng, L. Long, W. Chen, J. Yao, Y. Liu, *Frontiers in Aging Neuroscience* 18, 15 Oct 2026. 8 RCTs, 722 randomised; Hedges g: immediate near 0.14 (−0.23, 0.50; 6 trials N=376; very low certainty); immediate far 0.23 (−0.35, 0.81; 8 trials N=586; very low); sustained near −0.07 (−0.31, 0.18; 4 trials N=287; moderate); sustained far 0.02 (−0.26, 0.29; 5 trials N=397; moderate); immediate far without one trial (Wu et al.) g = 0.00 (−0.26, 0.25); functional far immediate −0.16 (−0.66, 0.33; 3 trials N=305). "Current evidence does not establish convincing durable transfer effects beyond trained processes." — [Frontiers](https://www.frontiersin.org/journals/aging-neuroscience/articles/10.3389/fnagi.2026.1952783/full)
- **Striking the Balance: How Variability Shapes Retrieval Practice and Worked Examples for Transfer Learning** — *Educational Psychology Review*, 12 May 2026 **[PRECURSOR; snippet only, paywall redirect]**: variability slowed learning and "did not lead to benefits in final generalization performance." — [Springer](https://link.springer.com/article/10.1007/s10648-026-10169-w)
- **Task, person, and experiential characteristics drive the transfer of learning** — *Communications Psychology* 2026 **[snippet only, paywall redirect]**: reviews that across perceptual, motor, and cognitive training, variability "robustly slows initial learning yet improves generalization"; individual emotion-cognition traits and stress physiology shape transfer; recommends structured variability tailored to the learner. — [Nature](https://www.nature.com/articles/s44271-026-00408-9)
- **Young children's learning of scientific explanations through brief analogical activities in a museum setting** — *Journal of Applied Developmental Psychology* 2026 (pii S0193397326000729) **[snippet only, 403]**: children learned explanations better when comparing an embodied experience with a scientific model; "Model Only" condition showed no significant improvement. — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0193397326000729)
- **Preschool analogical transfer despite misleading information (Bobrowicz group, Luxembourg)** — snippets describe 2.5–5.5-year-olds; transfer independent of age but predicted by world knowledge and working memory; a 2023 EARLI abstract (N=41 preliminary) found children under 40 months could not disregard irrelevant information. 2026 PsyArXiv version **not located** **[snippet only]**. Earlier journal version: *Cognitive Development* 2022, N=86. — [ORBilu](https://orbilu.uni.lu/handle/10993/57103); [PMC 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC10299410/)
- **Editorial: Understanding effective education: far transfer from a sociocultural and cognitive neural perspective** — 2026 **[snippet only]**: calls for identifying paradigms that reliably produce far transfer and their common features. — [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12894378/)
- **Neural representations supporting generalization under continual learning** — bioRxiv 2026.01.07.698044 **[PRECURSOR; snippet only]**: individual variation in a region's preferred level of abstraction predicted inference-based behaviour. — [bioRxiv](https://www.biorxiv.org/content/10.64898/2026.01.07.698044v1.full)
- **Mix & Gentner 2026** (see (b)) — practice recommendations grounded in progressive alignment and comparison **[snippet only]**.
- Background **[PRECURSOR]**: Gobet & Sala 2023, between- and within-study true variance in far transfer "small to null" — [Perspectives on Psych Sci](https://journals.sagepub.com/doi/10.1177/17456916221091830)

### Inferences
- Where far transfer appears in 2026 human work it comes from **explicit comparison of two aligned cases** (museum study; Gentner lineage), not from training on one case plus variability; and it is bounded by the learner's knowledge and working memory rather than age. The target system has unlimited "working memory" but no mechanism that *aligns* two worlds' cases; its carried statistics were marginal, not aligned.
- The null cognitive-training results reinforce that practicing a form (e.g., "explanations tend to be size 2") does not transfer; what transfers is a mapped relation.

### Gaps
- No 2026 animal far-transfer study found.
- No 2026 Cognition / Psychological Review / Nature Human Behaviour article on analogical far transfer surfaced in searches; the TACL 2026 survey (Petersen et al., "Modelling Analogies and Analogical Reasoning") exists but was not opened — [TACL](https://aclanthology.org/2026.tacl-1.32/).

---

## Key question 1: Is there a 2026 result where relational/structural alignment made a new domain faster without domain-specific hand-coding?

### Takeaway
Yes with an LLM in the loop (RoleWorld Oct 2026; ASPECT Apr 2026; Data Analogies Mar 2026 in robotics), **no** without one. The only LLM-free 2026 structure-mapping paper (SMTB) measures mapping quality, not learning speed.

### Cited Findings
- RoleWorld: role prototypes + fixed transition rules carried; parameters and role assignments re-inferred online; robust on MARS with altered object behaviour; LLM teacher/actor. — [arXiv 2610.13172](https://arxiv.org/abs/2610.13172)
- Data Analogies: paired cross-embodiment demos +22.5% real-world over unpaired large datasets; no LLM mapper but the pairs are supplied by the data designer (hand-coded correspondence). — [arXiv 2603.06450](https://arxiv.org/abs/2603.06450)
- Relational Transformer: zero-shot 93% of supervised AUROC on unseen DBs given column metadata; pretrained network, not symbolic. — [arXiv 2510.06377](https://arxiv.org/abs/2510.06377)
- SMTB: 5–15x faster than SME, +50% mapping success on large nested domains; no transfer test. — [arXiv 2609.25508](https://arxiv.org/abs/2609.25508)
- Executable World Models and Graph-Based Exploration: no carry across games at all. — [arXiv 2605.05138](https://arxiv.org/abs/2605.05138); [arXiv 2512.24156](https://arxiv.org/abs/2512.24156)

### Inferences
- The gap the target system sits in (symbolic, no LLM, cross-world) is empty in 2026 literature; a positive result there would be novel.

### Gaps
- None of the positive cases report learning-speed curves in their abstracts; PDFs not opened.

---

## Key question 2: Does any work explain why transferring a prior over explanation form fails while relational mapping of specific action pairs might work?

### Takeaway
No paper states this exact contrast, but three 2026 results jointly explain it: (i) label leakage — statistics learned from few tasks encode task-specific shortcuts (Azevedo et al.); (ii) exemplar retrieval does not yield second-order overhypotheses (Cacioli); (iii) what transfers in practice is (role, rule) with per-world parameters (RoleWorld) or explicit paired correspondences (Data Analogies), and meta-learned analogy reaches recombinations but not novel relations (Hellwig et al.).

### Cited Findings
- Limited task diversity, not data, constrains relational transfer; leakage degrades transfer even within the same schema. — [arXiv 2603.29914](https://arxiv.org/abs/2603.29914)
- 100% exemplar retrieval, 50–52% second-order generalization. — [arXiv 2604.05243](https://arxiv.org/abs/2604.05243)
- Role prototypes with fixed rules and free parameters generalize to altered object behaviour. — [arXiv 2610.13172](https://arxiv.org/abs/2610.13172)
- MLC analogy generalizes to compositions of trained transformations, "not to completely novel transformations." — [arXiv 2604.06501](https://arxiv.org/abs/2604.06501)
- Task diversity gives transfer at the start of a new distribution but a plateau later. — [arXiv 2606.00880](https://arxiv.org/abs/2606.00880)
- KPT 2007: an overhypothesis is a prior over a dimension that recurs with the same meaning across categories. — [PDF](https://www.mit.edu/~jbt/temp/KempPerforsTenenbaum.pdf)

### Inferences
- A prior over "explanation size / cell kind / outcome kind" is a prior over a dimension whose meaning changes per world (which cells exist, which outcomes exist), so by KPT's own logic it is not a valid overhypothesis across worlds; an action's *argument-role structure* (17/37 identical forms) is a dimension that does recur, so a mapping of specific action pairs with per-world parameters is the KPT-consistent unit.
- Six worlds is a low-diversity regime in Azevedo's sense; a form prior fit on them is likely a shortcut.

### Gaps
- No controlled 2026 study pits "form prior" against "pairwise relational mapping" in the same system.

---

## Key question 3: What does 2026 cognitive science say about the conditions for far transfer (comparison of several cases, variability, abstraction)?

### Takeaway
Comparison of aligned cases is the one condition still supported in 2026 (museum comparison study; Gentner-lineage guidance); variability is contested (one 2026 intervention finds no generalization benefit, one 2026 review says it robustly helps); abstraction level is identified as the bottleneck both in humans (bioRxiv neural abstraction level predicts inference) and machines (YARN); cognitive-training far transfer is null (g ≈ 0.02 sustained).

### Cited Findings
- Sustained far transfer g = 0.02 (−0.26, 0.29), 5 trials, N=397. — [Frontiers 2026](https://www.frontiersin.org/journals/aging-neuroscience/articles/10.3389/fnagi.2026.1952783/full)
- Variability slowed learning and did not improve final generalization (EdPsychRev, May 2026) [snippet only]. — [Springer](https://link.springer.com/article/10.1007/s10648-026-10169-w)
- Variability slows initial learning yet improves generalization; individual differences modulate (Comms Psych 2026) [snippet only]. — [Nature](https://www.nature.com/articles/s44271-026-00408-9)
- Comparison of embodied experience with model beats model alone in children (2026) [snippet only]. — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0193397326000729)
- Analogical transfer in 2.5–5.5-year-olds predicted by world knowledge and working memory, not age [snippet only]. — [ORBilu](https://orbilu.uni.lu/handle/10993/57103)
- Abstractions at the right level consistently improve structural mapping (YARN, Mar 2026). — [arXiv 2603.29997](https://arxiv.org/abs/2603.29997)
- Humans build reusable helpers online; helpers unlock otherwise impossible puzzles (Mar 2026). — [arXiv 2603.23244](https://arxiv.org/abs/2603.23244)

### Inferences
- For the target system the actionable 2026 conditions are: (1) align two worlds' concrete cases (not aggregate them), (2) carry reusable sub-explanations ("helpers") rather than form statistics, (3) expect benefit only where the new world's action is a recombination of mapped relations.

### Gaps
- CogSci 2026 proceedings content unverified (program PDF > fetch limit); Mix & Gentner 2026 body unread; paywalled Nature/Springer abstracts unread beyond snippets.
