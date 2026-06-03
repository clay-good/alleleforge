# Base editing (ABE / CBE) reference

Phase 8 adds the base-editing chemistry vertical — **enumerate -> window outcome
-> off-target -> candidate**. The hard part is the *window outcome*: which
editable base(s) in the activity window get edited, and what **bystanders** ride
along. From a resolved variant,
[`design_base_editor`][alleleforge.design.base_editor.design_base_editor] returns
candidates ranked by the probability of the **exact** intended allele while
minimizing bystander burden, flagging the cleanest combination as the
recommendation.

Only transition SNVs are base-editable: ABE installs A->G / T->C, CBE installs
C->T / G->A on the plus strand (editing the appropriate strand). The `BaseEditor`
registry is declarative — adding an editor is a data change.

!!! note "Transparent baseline, swappable for BE-DICT / BE-Hive"
    The shipped window-outcome model is a transparent, weight-free baseline
    (per-position editing probability × motif preference, positions independent).
    The trained BE-DICT (default) and BE-Hive models load through the
    license-gated model zoo.

## Editor registry & enumeration

::: alleleforge.enumerate.base_editor

## Window-outcome prediction

::: alleleforge.scoring.base_outcome

## The design vertical

::: alleleforge.design.base_editor
