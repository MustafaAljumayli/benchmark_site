r"""For every chart: the research question it answers, the formulas behind it, and how to read it.

The site shows the question above each chart and the formulas in a "How it's calculated" panel.
Formulas are Markdown with LaTeX ($...$ inline, $$...$$ on their own line), rendered by MathJax.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ChartNote:
    title: str
    question: str
    formulas: str   # Markdown + LaTeX
    reading: str    # how to read the chart, one or two sentences


# ---------------------------------------------------------------- shared formula blocks

LOG_SCALE = r"""
All scores are computed on the log scale, like CDC's evaluation: every observed value $y$ and every
quantile $q$ is replaced by $\log(1 + y)$ and $\log(1 + q)$ first. A forecast that is off by 20% then
costs about the same in a small state as in Texas.
"""

WIS = r"""
**Interval score.** For a central $(1-\alpha)$ interval $[l, u]$ (for the 95% interval, $\alpha = 0.05$,
$l = q_{0.025}$, $u = q_{0.975}$):

$$\mathrm{IS}_\alpha(y) = \underbrace{(u - l)}_{\text{width}} + \underbrace{\tfrac{2}{\alpha}(l - y)\,\mathbb{1}\{y < l\}}_{\text{missed low}} + \underbrace{\tfrac{2}{\alpha}(y - u)\,\mathbb{1}\{y > u\}}_{\text{missed high}}$$

**Weighted interval score (WIS)**, with median $m$ and the $K = 11$ intervals
98, 95, 90, 80, 70, 60, 50, 40, 30, 20, 10%:

$$\mathrm{WIS}(y) = \frac{1}{K + \tfrac{1}{2}}\left(\tfrac{1}{2}\,|y - m| + \sum_{k=1}^{K} \tfrac{\alpha_k}{2}\,\mathrm{IS}_{\alpha_k}(y)\right)$$

Lower is better. A narrow interval that contains $y$ scores well; missing $y$ costs $\tfrac{2}{\alpha}$ per
unit, so missing outside the 98% interval ($\tfrac{2}{0.02} = 100$ per unit) is punished far more than
missing outside the 50% interval ($4$ per unit).
""" + LOG_SCALE

PINBALL = r"""
**Why you may see "2 × pinball loss".** WIS can be written a second way, one quantile at a time.
The *pinball loss* of quantile $q$ at level $\tau$ is

$$\rho_\tau(y, q) = \begin{cases} \tau\,(y - q) & y \ge q \text{ (the quantile was too low)} \\ (1 - \tau)\,(q - y) & y < q \text{ (the quantile was too high)} \end{cases}$$

It charges a 90% quantile 0.9 per unit when it is too low and only 0.1 per unit when it is too high,
because a 90% quantile *should* be above the outcome 90% of the time.

Each interval term is exactly the pinball loss of its two quantiles added together,
$\tfrac{\alpha}{2}\mathrm{IS}_\alpha(y) = \rho_{\alpha/2}(y, l) + \rho_{1-\alpha/2}(y, u)$, and the median term is
$\tfrac{1}{2}|y - m| = \rho_{0.5}(y, m)$. So the bracket in WIS is the pinball loss summed over all 23
quantiles, and dividing by $K + \tfrac{1}{2} = 11.5 = 23 / 2$ is the same as

$$\mathrm{WIS}(y) = \frac{1}{23}\sum_{i=1}^{23} 2\,\rho_{\tau_i}(y, q_i)$$

the average of *twice* the pinball loss. The 2 is only there so both formulas give the same number.
The code uses the interval form above, which is how CDC defines it.

*Example* (one interval, plain counts): 50% interval $[80, 120]$, $y = 130$. Interval form:
$\tfrac{0.5}{2}\big(40 + \tfrac{2}{0.5}\cdot 10\big) = 20$. Pinball form:
$\rho_{0.25}(130, 80) + \rho_{0.75}(130, 120) = 0.25\cdot 50 + 0.75\cdot 10 = 20$.
"""

SHARED_TASKS = r"""
Models are compared only on the forecasts they **all** made: the same reference dates, locations and
horizons 0-3 (horizon −1 is not scored). A model that skipped hard weeks can't look better by skipping.
"""

QUANTILE_INTERVALS = r"""
| Interval | lower quantile | upper quantile | $\alpha$ |
|---|---|---|---|
| 98% | 0.01 | 0.99 | 0.02 |
| 95% | 0.025 | 0.975 | 0.05 |
| 90% | 0.05 | 0.95 | 0.10 |
| 80% | 0.10 | 0.90 | 0.20 |
| 70% | 0.15 | 0.85 | 0.30 |
| 60% | 0.20 | 0.80 | 0.40 |
| 50% | 0.25 | 0.75 | 0.50 |
| 40% | 0.30 | 0.70 | 0.60 |
| 30% | 0.35 | 0.65 | 0.70 |
| 20% | 0.40 | 0.60 | 0.80 |
| 10% | 0.45 | 0.55 | 0.90 |

Together with the median (0.5) these are the 23 quantiles every FluSight forecast has.
"""


# ---------------------------------------------------------------- one note per chart

NOTES = {
    "forecast": ChartNote(
        title="Forecasts against what happened",
        question="How did each model's center and uncertainty compare with what was eventually reported, and how "
                 "much did later revisions change the most recent data the model saw?",
        formulas=r"""
For each horizon $h \in \{-1, 0, 1, 2, 3\}$ the line is the median $q_{0.5}$ and each band is a central
interval $[q_{(1-c)/2},\, q_{(1+c)/2}]$ for coverage $c$:
""" + QUANTILE_INTERVALS + r"""
With all 11 bands on, each band has opacity $0.06$, so a point inside $k$ bands has opacity
$1 - (1 - 0.06)^k$: darkest at the median, faintest at the 98% interval.
""",
        reading="Diamonds inside the darkest part of a model's fan were forecast confidently and correctly. "
                "Turn on 'as reported then' to compare the data the model saw with the final data.",
    ),

    "rate_surface": ChartNote(
        title="Flu across states, week by week (3D)",
        question="Which states carry the heaviest flu burden, when does each state's season peak, and do the "
                 "model's forecasts follow that pattern across states?",
        formulas=r"""
Built the same way as the state heatmap in `notebooks/data_analysis.ipynb`:

$$\text{rate}_{s,w} = \frac{\text{admissions}_{s,w}}{\text{population}_s} \times 100{,}000, \qquad
z_{s,w} = \log(1 + \text{rate}_{s,w})$$

States (the US total left out) are sorted by their mean rate over the weeks shown, highest first:
$\bar r_s = \frac{1}{W}\sum_w \text{rate}_{s,w}$. The log keeps high-burden weeks from flattening
everything else. (Her heatmap is colored with viridis; this surface uses the site's blue scale.)

The dots are the model's median forecasts for horizons 0-3 at the round on the slider, on the same scale:
$\hat z = \log\!\left(1 + q_{0.5} / \text{population}_s \times 100{,}000\right)$, with
$\text{population}_s$ = the median over weeks of $\text{admissions}_{s,w} / \text{rate}_{s,w} \times 100{,}000$.
""",
        reading="Ridges running across states show a national wave; a ridge in only a few rows is a regional "
                "outbreak. Dots floating above the surface are over-forecasts, dots buried in it are under-forecasts.",
    ),

    "score_timeline": ChartNote(
        title="Score over the season",
        question="Which model forecast best each week, and when in the season did each model lose accuracy?",
        formulas=WIS + r"""
**Per round.** For round $t$, with $T_t$ the shared forecasts made that round:
$\overline{\mathrm{WIS}}_t = \frac{1}{|T_t|}\sum_{j \in T_t} \mathrm{WIS}_j$.

**Relative to the baseline** (when switched on): $\overline{\mathrm{WIS}}_t^{\,\text{model}} \big/ \overline{\mathrm{WIS}}_t^{\,\text{baseline}}$;
below 1 is better than FluSight-baseline.
""" + PINBALL + SHARED_TASKS,
        reading="Lower is better. Spikes usually line up with the season's turning points (the rise and the peak).",
    ),

    "horizon_summary": ChartNote(
        title="By horizon, season to date",
        question="How quickly does each model's accuracy degrade the further ahead it forecasts?",
        formulas=r"""
For horizon $h$ and the round $t$ on the slider, the mean over every shared forecast made up to that round:

$$\overline{\mathrm{WIS}}_{h}(t) = \frac{1}{|\{j : t_j \le t,\ h_j = h\}|}\sum_{t_j \le t,\ h_j = h} \mathrm{WIS}_j$$

Relative view: the same mean divided by FluSight-baseline's.
""" + SHARED_TASKS,
        reading="Bars should rise from h0 to h3. A model whose bars rise faster than the baseline's loses its edge "
                "at longer horizons.",
    ),

    "coverage": ChartNote(
        title="Calibration",
        question="Are each model's uncertainty intervals the right width: do its c% intervals contain what "
                 "happened c% of the time?",
        formulas=r"""
For each of the 11 central intervals $c$, over every shared forecast up to the round on the slider:

$$\text{coverage}_c = \frac{1}{N}\sum_{j=1}^{N} \mathbb{1}\{\,q^{(j)}_{(1-c)/2} \le y_j \le q^{(j)}_{(1+c)/2}\,\}$$
""" + QUANTILE_INTERVALS + SHARED_TASKS,
        reading="On the diagonal is calibrated. Below it, intervals are too narrow (overconfident); above it, too wide.",
    ),

    "error_surface": ChartNote(
        title="Error by round and horizon (3D)",
        question="When in the season, and at which horizons, did the errors concentrate, and do both models "
                 "struggle at the same time?",
        formulas=r"""
Height at round $t$ and horizon $h$ = mean WIS over the shared forecasts for that round and horizon,
averaged over locations: $\overline{\mathrm{WIS}}_{t,h}$.
""" + SHARED_TASKS,
        reading="Ridges along the round axis are hard weeks for everyone; a ridge that grows toward h3 means "
                "the model can't see turning points far ahead.",
    ),

    "state_map": ChartNote(
        title="Benchmarks by state",
        question="In which states does the model beat, or lose to, the CDC baseline, and is that changing as the "
                 "season goes on?",
        formulas=r"""
Season to date for state $s$ at the round $t$ on the slider (forecasts made up to $t$, horizons 0-3):

**vs FluSight-baseline**

$$\theta_s(t) = \frac{\frac{1}{N}\sum_j \mathrm{WIS}^{\text{model}}_j}{\frac{1}{N}\sum_j \mathrm{WIS}^{\text{baseline}}_j}$$

over the forecasts both made. The color is $\log_2 \theta_s$, so twice as good and twice as bad sit
equally far from gray. (CDC's official relative WIS combines ratios between every pair of models; this
is the simple ratio against the baseline.)

**log-WIS**: $\frac{1}{N}\sum_j \mathrm{WIS}_j$. **95% coverage**: share of 95% intervals with
$q_{0.025} \le y \le q_{0.975}$; 95% is calibrated.
""",
        reading="Click a state on the map or a row in the table to select it; every other chart follows.",
    ),

    "leaderboard": ChartNote(
        title="Model leaderboard",
        question="How does every FluSight model, ours included, rank on this season's forecasts, and do our "
                 "scores reproduce CDC's official evaluation?",
        formulas=r"""
**Which forecasts.** Weekly flu admissions, horizons 0-3, for the 50 states, DC and Puerto Rico (the US total
is left out, as in CDC's report; choose a Location to rank one place instead), at every reference date
FluSight-baseline forecast this season.

**Pairwise relative WIS** (Cramer et al. 2022, the method in CDC's FluSight reports). Models skip different
weeks and places, so every pair of models $i, j$ is compared only on the forecasts both made:

$$r_{ij} = \frac{\overline{\mathrm{WIS}}_i}{\overline{\mathrm{WIS}}_j} \quad\text{(means over the forecasts } i \text{ and } j \text{ share)}$$

Each model's score is the geometric mean of its ratios to every hub model $j$ it shares forecasts with,
divided by the baseline's:

$$\theta_i = \Big(\prod_{j} r_{ij}\Big)^{1/n_i}, \qquad \text{relative WIS}_i = \frac{\theta_i}{\theta_{\text{FluSight-baseline}}}$$

**Log relative WIS** uses WIS on $\log(1 + y)$ (CDC ranks by this); **relative WIS** uses WIS on the counts.
Our backtests are compared with every hub model the same way, but are not part of the pool, so the hub
models' scores stay exactly CDC's.

**WIS**, **MAE** (absolute error of the median) and **coverage** are plain means over each model's own
forecasts, on the counts, so they are only comparable between models that forecast the same weeks.

**Scored against.** *CDC end-of-season evaluation*: CDC's official rules for the season (flusight/cdc_evaluation.py):
national and (from 2024/25) Puerto Rico forecasts left out, models with under 75% of the forecasts left out of
the pool, the truth release CDC scored against; our relative WIS matches CDC's published table for every model.
Backtests are ranked as if submitted; they are retrospective, so their rank is optimistic. *Latest data* and
*Hub weekly report*: the hub's in-season report rules described above (Puerto Rico in, no 75% rule), which are
not CDC's official evaluation.
""",
        reading="Shorter bars are better; the dotted line is FluSight-baseline. Check \"Forecasts scored\" before "
                "trusting a rank: a model scored on a handful of forecasts can land anywhere.",
    ),

    "summary_table": ChartNote(
        title="Summary table",
        question="Overall, how does each model rank on the forecasts they all made?",
        formulas=r"""
Mean log-WIS over all shared forecasts and per horizon; *vs FluSight-baseline* is the ratio of means;
*inside 50% / 95%* are the coverage shares defined in the calibration chart.
""" + SHARED_TASKS,
        reading="Sorted best first by mean log-WIS.",
    ),

    "run_history": ChartNote(
        title="Every saved run",
        question="Is each change to our models making the backtest better or worse?",
        formulas=r"""
Each point is one saved run (`run-<number>-<model>`), at its mean WIS over every forecast it made:
$\frac{1}{N}\sum_j \mathrm{WIS}_j$ (log scale, horizons 0-3, scored against the final data).
Runs that cover different rounds are not directly comparable; check the rounds in the table.
""",
        reading="Run numbers only go up, so the chart reads left to right as the project's history.",
    ),
}


def note(chart_id: str) -> ChartNote:
    return NOTES[chart_id]
