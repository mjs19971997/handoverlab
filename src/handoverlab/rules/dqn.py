# SPDX-License-Identifier: MIT
"""A deep Q-network that chooses the A3 offset of every user (optional PyTorch; since 1.11.0).

``pip install handoverlab[torch]`` installs PyTorch; ``import handoverlab``
does not need it, and only building the rule imports it.

The rule is Event A3 (TS 38.331 clause 5.5.4.4) with a fixed time-to-trigger
whose offset a Q-network picks per user from ``offsets_db``.  A decision step
of a user lasts from one handover (or link failure) to the next:

* state, from what the network observes: the serving cell's L3 RSRP, the three
  best neighbour-minus-serving differences and the reported speed (scaled);
* action: the A3 offset used until the user's next handover;
* reward, when the outcome of that handover is known: useful +1, unnecessary
  ``-w_unnecessary``, early or late ``-w_failure``; a link failure without a
  handover counts as ``-w_failure`` (the labels of mobility robustness
  optimisation, TS 38.300 clause 15.5.2, as for ``a3_bandit``);
* next state: the state at the instant after the handover.

Learning (``mode="train"``) is Q-learning with a replay buffer and a target
network (Mnih et al., Nature 518, 2015): epsilon-greedy actions, one gradient
step on a random batch every ``train_every`` new transitions, the target
network copied every ``target_every`` steps.  ``mode="test"`` acts greedily
and does not learn.  ``weights`` names a file of trained weights (written by
:func:`train`); training starts from it if given.

Reproducibility: CPU only, ``torch.use_deterministic_algorithms(True)``, one
thread during every forward and backward pass, the network initialised under a
seed drawn from ``ctx.rng`` and batches drawn from ``ctx.rng``; PyTorch's and
NumPy's global random states are left unchanged.  Two runs on one machine and
PyTorch version give identical event logs; other hardware or versions may give
other results, so there is no golden fingerprint for this rule.
"""
from __future__ import annotations

import contextlib
from typing import Any, Dict, Optional, Sequence

import numpy as np

from .base import EARLY, LATE, UNNECESSARY, USEFUL, BaselineRule

N_FEATURES = 5
INSTALL_HINT = "the rule 'dqn' needs PyTorch: pip install handoverlab[torch]"


def _torch():
    try:
        import torch
    except ImportError as e:                                  # pragma: no cover - depends on the installation
        raise ImportError(INSTALL_HINT) from e
    return torch


def available() -> bool:
    """True if PyTorch can be imported."""
    try:
        _torch()
        return True
    except ImportError:
        return False


@contextlib.contextmanager
def _one_thread(torch):
    n = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(n)


def features(obs) -> np.ndarray:
    """State of every user (U, 5): serving RSRP, three best neighbour differences and speed, scaled to about +-1."""
    U, M = obs.gap_db.shape
    serv = obs.meas_dbm[np.arange(U), obs.serving]
    gap = np.array(obs.gap_db, dtype=float)
    gap[np.arange(U), obs.serving] = -np.inf
    k = min(3, M - 1)
    top = -np.sort(-gap, axis=1)[:, :k] if k > 0 else np.empty((U, 0))
    top = np.where(np.isfinite(top), top, -30.0)
    if k < 3:
        top = np.hstack([top, np.full((U, 3 - k), -30.0)])
    out = np.empty((U, N_FEATURES))
    out[:, 0] = (serv + 100.0) / 20.0
    out[:, 1:4] = top / 10.0
    out[:, 4] = obs.speed / 30.0
    return out


class DQNA3(BaselineRule):
    """Event A3 whose offset a deep Q-network chooses per user (see the module text).

    offsets_db     the A3 offsets the network chooses from [dB]
    ttt_s          time-to-trigger [s]
    mode           "train" (learn, epsilon-greedy) or "test" (greedy, no learning)
    weights        file of trained weights to start from (or None: random initial weights)
    hidden         units of each of the two hidden layers
    lr             learning rate of the Adam optimiser
    gamma          discount of the next decision step
    epsilon        exploration probability while training
    batch          transitions per gradient step
    buffer         size of the replay buffer
    train_every    new transitions per gradient step
    target_every   gradient steps between copies to the target network
    w_unnecessary  penalty of an unnecessary handover
    w_failure      penalty of an early or late handover or a link failure
    """
    learns = True
    requires = "PyTorch (pip install handoverlab[torch])"
    installed = staticmethod(available)

    def __init__(self, offsets_db: Sequence[float] = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0), ttt_s: float = 0.16,
                 mode: str = "train", weights: Optional[str] = None, hidden: int = 32, lr: float = 1e-3,
                 gamma: float = 0.9, epsilon: float = 0.1, batch: int = 32, buffer: int = 5000, train_every: int = 4,
                 target_every: int = 100, w_unnecessary: float = 1.0, w_failure: float = 2.0, name: str = "A3-DQN"):
        super().__init__(name)
        self.offsets_db = [float(o) for o in offsets_db]
        if not self.offsets_db:
            raise ValueError("offsets_db needs at least one offset")
        if mode not in ("train", "test"):
            raise ValueError("mode must be 'train' or 'test'")
        if not 0.0 <= epsilon <= 1.0 or not 0.0 <= gamma < 1.0 or ttt_s < 0:
            raise ValueError("epsilon must be in [0, 1], gamma in [0, 1) and ttt_s >= 0")
        if min(int(hidden), int(batch), int(buffer), int(train_every), int(target_every)) < 1 or lr <= 0:
            raise ValueError("hidden, batch, buffer, train_every and target_every must be >= 1 and lr > 0")
        self.ttt_s, self.mode, self.weights = float(ttt_s), mode, weights
        self.hidden, self.lr, self.gamma, self.epsilon = int(hidden), float(lr), float(gamma), float(epsilon)
        self.batch, self.buffer, self.train_every, self.target_every = int(batch), int(buffer), int(train_every), \
            int(target_every)
        self.w_unnecessary, self.w_failure = float(w_unnecessary), float(w_failure)
        _torch()                            # fails early with a clear message without PyTorch
        self.net = None                     # built at the first reset and kept by train()

    def params(self) -> Dict[str, Any]:
        return dict(offsets_db=list(self.offsets_db), ttt_s=self.ttt_s, mode=self.mode, weights=self.weights,
                    hidden=self.hidden, lr=self.lr, gamma=self.gamma, epsilon=self.epsilon, batch=self.batch,
                    buffer=self.buffer, train_every=self.train_every, target_every=self.target_every,
                    w_unnecessary=self.w_unnecessary, w_failure=self.w_failure)

    # ------------------------------------------------------------------ network
    def _build(self, seed: int) -> None:
        torch = _torch()
        nn = torch.nn
        K = len(self.offsets_db)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.net = nn.Sequential(nn.Linear(N_FEATURES, self.hidden), nn.ReLU(), nn.Linear(self.hidden, self.hidden),
                                     nn.ReLU(), nn.Linear(self.hidden, K)).double()
        if self.weights:
            self.net.load_state_dict(torch.load(self.weights, weights_only=True))
        self.target = nn.Sequential(nn.Linear(N_FEATURES, self.hidden), nn.ReLU(), nn.Linear(self.hidden, self.hidden),
                                    nn.ReLU(), nn.Linear(self.hidden, K)).double()
        self.target.load_state_dict(self.net.state_dict())
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        self.n_steps = 0
        self.replay = []                    # (s, a, r, s') tuples, oldest first
        self.n_new = 0

    def save(self, path: str) -> None:
        """Write the weights of the Q-network to ``path`` (to be used as ``weights``)."""
        _torch().save(self.net.state_dict(), path)

    def q_values(self, states: np.ndarray) -> np.ndarray:
        """Q-values (N, K) of states (N, 5)."""
        torch = _torch()
        with torch.no_grad(), _one_thread(torch):
            return self.net(torch.from_numpy(np.asarray(states, dtype=np.float64))).numpy()

    # ------------------------------------------------------------------ rule hooks
    def reset(self, ctx):
        super().reset(ctx)
        torch = _torch()
        torch.use_deterministic_algorithms(True)
        seed = int(ctx.rng.integers(2 ** 31 - 1))
        if self.net is None:
            self._build(seed)
        U = ctx.n_users
        self.act = np.full(U, -1, dtype=int)            # offset index of every user; -1: a new step is due
        self.serv = np.full(U, -1, dtype=int)
        self.cur = np.full(U, -1, dtype=int)           # id of the open decision step of every user
        self.steps: Dict[int, list] = {}               # id -> [state, action, reward or None, next state or None]
        self.ended: Dict[int, list] = {}               # user -> ids of steps ended by a link failure
        self._next_id = 0
        self.n_decisions = 0
        self.total_reward, self.n_rewards = 0.0, 0

    def _choose(self, s: np.ndarray) -> np.ndarray:
        q = self.q_values(s)
        a = np.argmax(q, axis=1)
        if self.mode == "train" and self.epsilon > 0:
            explore = self.ctx.rng.random(len(a)) < self.epsilon
            if explore.any():
                a[explore] = self.ctx.rng.integers(len(self.offsets_db), size=int(explore.sum()))
        return a

    def _complete(self, sid: int) -> None:
        """Move a step with its reward and next state into the replay buffer (and learn while training)."""
        s, a, r, s2 = self.steps.pop(sid)
        if self.mode != "train":
            return
        self.replay.append((s, a, r, s2))
        if len(self.replay) > self.buffer:
            self.replay.pop(0)
        self.n_new += 1
        if self.n_new >= self.train_every and len(self.replay) >= self.batch:
            self.n_new = 0
            self._learn()

    def _learn(self) -> None:
        torch = _torch()
        idx = self.ctx.rng.integers(len(self.replay), size=self.batch)
        s = torch.from_numpy(np.array([self.replay[i][0] for i in idx]))
        a = torch.from_numpy(np.array([self.replay[i][1] for i in idx], dtype=np.int64))
        r = torch.from_numpy(np.array([self.replay[i][2] for i in idx], dtype=np.float64))
        s2 = torch.from_numpy(np.array([self.replay[i][3] for i in idx]))
        with _one_thread(torch):
            with torch.no_grad():
                y = r + self.gamma * self.target(s2).max(dim=1).values
            q = self.net(s).gather(1, a[:, None])[:, 0]
            loss = torch.nn.functional.smooth_l1_loss(q, y)
            self.opt.zero_grad()
            loss.backward()
            self.opt.step()
        self.n_steps += 1
        if self.n_steps % self.target_every == 0:
            self.target.load_state_dict(self.net.state_dict())

    def a3_offsets(self, obs):
        # a decision step ends at a handover (the serving cell changes) or a link failure; a new one starts
        need = obs.connected & ((obs.serving != self.serv) | (self.act < 0))
        if need.any():
            users = np.flatnonzero(need)
            s = features(obs)[users]
            for k, u in enumerate(users):
                ended = self.ended.pop(int(u), [])
                if self.cur[u] >= 0:
                    ended.append(int(self.cur[u]))
                for sid in ended:                       # their next state is the state now
                    st = self.steps.get(sid)
                    if st is not None and st[3] is None:
                        st[3] = s[k].copy()
                        if st[2] is not None:
                            self._complete(sid)
            a = self._choose(s)
            for k, u in enumerate(users):
                self.steps[self._next_id] = [s[k].copy(), int(a[k]), None, None]
                self.cur[u] = self._next_id
                self._next_id += 1
            self.act[users] = a
            self.n_decisions += len(users)
        self.serv = np.where(obs.connected, obs.serving, self.serv)
        off = np.asarray(self.offsets_db)[np.maximum(self.act, 0)]
        return np.repeat(off[:, None], obs.gap_db.shape[1], axis=1)

    def time_to_trigger(self, obs):
        return self.ttt_s

    def memory_key(self, obs):
        return self.cur.copy()

    def reward(self, label: int) -> float:
        """Reward of an outcome label."""
        if label == USEFUL:
            return 1.0
        if label == UNNECESSARY:
            return -self.w_unnecessary
        if label in (EARLY, LATE):
            return -self.w_failure
        return 0.0

    def _reward(self, sid: int, r: float) -> None:
        st = self.steps.get(sid)
        if st is None or st[2] is not None:            # unknown or already rewarded step
            return
        st[2] = r
        self.total_reward += r
        self.n_rewards += 1
        if st[3] is not None:
            self._complete(sid)

    def on_outcome(self, rec):
        self._reward(int(rec.key), self.reward(rec.label))

    def on_link_failure(self, rec):
        u = int(rec.user)
        sid = int(self.cur[u])
        if sid >= 0:
            self._reward(sid, -self.w_failure)
            self.ended.setdefault(u, []).append(sid)
        self.cur[u] = -1
        self.act[u] = -1                               # a new decision step after the re-establishment


def train(scenario, seeds: Sequence[int], path: Optional[str] = None, **params) -> DQNA3:
    """Train one :class:`DQNA3` over the worlds of ``seeds`` in turn (keeping its network) and save it to ``path``.

    Use seeds that never appear among the test seeds.  Returns the trained rule; test it with
    ``{"rule": "dqn", "mode": "test", "weights": path}``.
    """
    from ..channel.source import RadioSource
    from ..engine.core import Engine
    from ..world import build_world
    rule = DQNA3(mode="train", **params)
    for seed in seeds:
        world = build_world(scenario, int(seed))
        eng = Engine(world, rule, False, None)
        for ch in RadioSource(world).chunks():
            eng.advance(ch)
        eng.finish()
    if path:
        rule.save(path)
    return rule
