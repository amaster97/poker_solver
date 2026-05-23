# Rust orientation for this project

A focused 3–5 day primer to make you productive on **just** the parts of Rust that the CFR core touches. Not a deep Rust course — enough that the Rust crate at `crates/cfr_core/` is readable + editable for you.

You should be productive in the Python tier (`poker_solver/`) from day one because it's just Python. This doc only covers the Rust side.

---

## What you'll touch in Rust (and only this)

The Rust crate is small by design — most of the codebase is Python. Rust holds the CFR inner loop (regret tables, DCFR iteration, average strategy updates) and the hand evaluator port. That's it. Concretely you'll see:

- `Vec<f64>` arrays for regrets and strategies
- `HashMap<String, InfosetData>` for the infoset lookup table
- A small handful of structs (`KuhnState`, `InfosetData`, `DCFRSolver`)
- A few `#[pyfunction]` and `#[pyclass]` PyO3 macros at the FFI boundary
- Iterator chains over collections
- A few SIMD intrinsics in the perf-critical hot loop (later, in PR 8)

No async, no traits beyond what's auto-derived, no lifetimes annotations except where the compiler insists.

---

## Day 1 — Read

1. **The Rust book** *(skim, don't memorize):* chapters 3 (variables, types), 4 (ownership), 6 (enums + match), 8 (collections), 13 (iterators), 17 (closures vaguely). Skip async, lifetimes-deep-dive, advanced traits. https://doc.rust-lang.org/book/
2. **Rustlings** *(do, don't just read):* the first ~40 exercises (variables, primitive types, structs, enums, iterators, error handling). https://github.com/rust-lang/rustlings — `cargo install rustlings && rustlings init`

You'll find ownership / borrowing is the only conceptually new thing vs Python. Everything else is "stricter, more explicit Python."

---

## Day 2 — Mental model: ownership, borrows, and what they prevent

Python: `a = [1, 2]; b = a; b.append(3)` — `a` is mutated too (shared reference).

Rust default: `a` and `b` cannot both exist mutably at the same time. Either `b` *takes ownership* of the vector (then `a` is no longer usable) or `b` *borrows* it (`&a` for immutable, `&mut a` for mutable, and only one mutable borrow at a time).

The compiler enforces this. It feels annoying for a week. Then it becomes free, and you stop having concurrency bugs.

**The three patterns you'll see 95% of the time in our crate:**

1. **Owned value:** `let infosets: HashMap<...> = HashMap::new();` — owned, lives until the function returns or you move it.
2. **Immutable borrow:** `fn foo(state: &KuhnState)` — read-only access; the caller still owns the value.
3. **Mutable borrow:** `fn update_regrets(info: &mut InfosetData, ...)` — exclusive write access; only one `&mut` at a time.

---

## Day 3 — PyO3 macros (the only "magic" you'll see)

The Rust↔Python bridge uses `pyo3`. Two macros do most of the work:

```rust
#[pyfunction]
fn solve_kuhn(iterations: u32, alpha: f64, beta: f64, gamma: f64) -> PyResult<PyObject> {
    // Rust code; returns a Python object
}

#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve_kuhn, m)?)?;
    Ok(())
}
```

That's the entire FFI surface for PR 1. You write Rust; PyO3 generates the C ABI shims so Python's `import poker_solver._rust` works.

For `pyclass` (exposing a Rust struct as a Python class), the same idea but slightly more boilerplate. We won't need it for PR 1.

PyO3 quickstart: https://pyo3.rs/

---

## Day 4 — Differential testing pattern

You'll build the Python reference first, validate it, then port to Rust. The diff-test asserts the two implementations agree numerically on small games. When they disagree:

1. Pick the smallest input that exposes the divergence (e.g. 1 iteration, 1 infoset).
2. Print intermediate values from both implementations at every step.
3. Find the first step where they diverge.
4. That's where the bug is — usually a math mistake or an off-by-one in iteration.

**Never widen the diff-test tolerance to make a real divergence "pass."** That hides bugs.

---

## Day 5 — Just try it

Write a tiny throwaway PyO3 project. Suggested:

```bash
cd /tmp
maturin new --bindings pyo3 my_first_rust
cd my_first_rust
# Edit src/lib.rs to add a function that sums a Vec<f64>
pip install -e .
python -c "from my_first_rust import sum_vec; print(sum_vec([1.0, 2.0, 3.0]))"
```

Once that works end-to-end, you've removed all the toolchain magic and you're ready for PR 1.

---

## Things you can ignore for a long time

- Async / tokio
- Lifetimes annotations (the compiler usually infers; you'll only need `'a` syntax in advanced cases)
- Custom traits + generics (we'll use built-in traits)
- `unsafe` blocks (project rule: never without a `// SAFETY:` comment)
- Cargo workspaces deep-dive (we have one workspace; it just works)
- Procedural macros beyond PyO3's
- Lifetime elision rules (just write code; the compiler tells you when it can't infer)

---

## Cheat sheet (the patterns you'll actually use)

```rust
// Vec creation + filling
let mut regrets: Vec<f64> = vec![0.0; num_actions];

// HashMap creation + insert/lookup
use std::collections::HashMap;
let mut infosets: HashMap<String, InfosetData> = HashMap::new();
infosets.insert("12|".to_string(), InfosetData::new(2));
let entry = infosets.entry("12|".to_string()).or_insert_with(|| InfosetData::new(2));

// Iterator chain (sum positive regrets)
let total: f64 = regrets.iter().filter(|&&r| r > 0.0).sum();

// Match on enum
match state {
    KuhnState::Terminal(utility) => utility,
    KuhnState::Chance(_) => { /* sample chance */ }
    KuhnState::Player(_) => { /* recurse */ }
}

// PyO3 dict return
use pyo3::types::PyDict;
let dict = PyDict::new(py);
dict.set_item("game_value", -1.0/18.0)?;
Ok(dict.into())
```

---

## When you're stuck

Three good places:
- The Rust compiler's error messages (genuinely helpful — read them carefully)
- `rust-analyzer` in your editor (autocomplete, inline types)
- `rustc --explain E0382` (for any error code; gives a long explanation)

And me. I'll be writing most of the Rust; you'll be reading + editing.
