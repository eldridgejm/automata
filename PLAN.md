# Plan

In this branch, we will implement the website feature "from scratch". We have already developed a proof of concept in the "proof_of_concept" branch, which demonstrated the core functionality.

- [x] Website abstraction (structure of the input and output)
- [x] The RenderContext abstraction
- [x] Low-level single page renderers (for use with, e.g., the practice problem generator)
- [x] Config type
- [x] generate() signature
- [x] Simple website generation (markdown to HTML)
- [x] Convert HTML files as well?
  - maybe they have frontmatter
  - maybe they have a special extension, like `.html.unrendered`?
- [x] Searching for materials in the content directory
- [x] Allow overriding markdown renderer
- [x] Page frontmatter
- [x] Base path handling
- [x] The "theme" abstraction
- [x] Theme extensions as entry points
- [x] Theme overrides (templates and static files)
- [x] The "element" abstraction
- [x] Make new design
- [x] Start placing new design in the default theme
- [x] Override tailwind typography defaults for links, headings, etc.
- [x] Reworked schedule element
    - [x] Make it easier to provide link to artifact
    - [x] Make schedule tests pass
    - [x] Implement different types of resources
    - [x] Implement "extra" primary/secondary content
    - [-] Implement "extra" resources?
    - [x] Implement due dates for all content types (primary, secondary, extra)
    - [x] Allow things to display in future weeks? E.g., if an assignment is due in week 5 and is released in week 3, should it show up in week 3 or week 5? (Or every week in between?)
    - [x] Figure out a better name for "content" (e.g., what is a homework, lecture, etc. Component?
    - [x] Determine whether `display_starting_on` should be `display_starting_at` and accept a datetime instead of a date. Same for other date fields.
    - [x] Implement a `!metadata_key` function for use in schedule config
    - [x] Better styling for "future weeks" divider
- [x] Implement date_pill element
- [-] Simplify the second integration test?
- [-] "Install" lucide icons so that we don't need to use the CDN
- [x] Implement `!` tags in config reader
- [x] Figure out what controls whether something shows up in schedule yet
- [x] Extract the logic tests for schedule to tests of the builtin_elements module.
- [x] Change signature of generate() to accept the path to the materials directory
    - Copy it if it is outside of the content directory; otherwise just use it directly
- [x] Update build() to export the materials to a temporary directory and pass that to generate()
- [x] Enable more markdown features (TOC, admonitions, etc.), in a way that is extensible.
- [x] Build hooks (allowing scripts to run at certain points in the generation process)
- [x] Remove ability for script hooks to return output (only some hooks will be valid script hooks)
- [x] If extension directory contains a __init__.py file, treat it as a package and add it to sys.path. Otherwise, treat it as a "filesystem extension".
- [x] More clearly define the notions of "filesystem extensions" vs "package extensions" and clearly document the structure of a filesystem extension. Maybe rename the methods that load extensions to reflect this distinction?
- [x] Is "priority" the best way to control the order in which extensions are applied? 100 is the lowest priority, meaning it runs last, but isn't that "higher" priority in a sense because it will override other extensions?
- [x] Allow extensions to specify additional resolve functions, global functions available during resolution.
    - we will handle this with hooks
- [x] Whenever we pass a lot of arguments to execute_hook, we should consider passing them as kwargs instead.
- [x] Rename "plugin" to "extension"
- [ ] Rename "static_files" to "assets"
- [ ] Explore reorganizing hooks module into a subpackage
- [ ] Rename "build()" to "generate()"?
- [ ] Make sure all tests are in pytest style
- [ ] Investigate issue with npx not being found
- [ ] Improve test coverage
- [ ] Add checks to make sure that artifacts that are released and then unreleased do not still appear in the materials.
- [ ] Improve the listing element by moving more of the logic outside of the template
- [ ] Thorough documentation of website abstraction
- [ ] Thorough documentation of default theme, including elements
- [ ] Better error messages
- [ ] Flesh out the CLI with more commands

---

# Feature: start_location and end_location for schedule listings

Currently, there is one way to control where publications appear on the schedule: via the
`metadata_key_for_released` field in the schedule configuration. This field specifies which metadata key to use for determining the release date of a publication. To place
the publication in the schedule, the week containing the date in that metadata key is
determined and the publication is listed in that week.

This approach has some limitations. First, it means that a publication can only appear
in one week. This is sometimes not ideal. For example, suppose a homework is
released on Sunday, January 11 (which happens to be the last day of Week 1). It is due
on Sunday, January 18 (the last day of Week 2). Using the current approach, the publication release date is January 11, so it appears in Week 1. However, it would be more useful to have it appear in Week 2, since the majority of the time that the homework is relevant is during Week 2.

Other use cases include:

- We will release a publication's artifacts on a future date, but we want it to appear on the schedule starting from today.
- We want to release a publication "after the fact". Meaning, it will start showing on the
schedule at some time in the future, but it will show up in the section for a past week.

To support a more flexible approach, we will implement three configuration fields:

- `start_displaying_on`: The date when the publication should start appearing on
  the schedule. This does not determine *where* the publication appears; that
  is determined by the following fields.
- `start_location` and `end_location`: dates that determine the start and end weeks, described below. `end_location` must be on or after `start_location`.

On the date given by `start_displaying_on`, the publication will start appearing on the schedule. Where it will appear is determined by the `start_location` and `end_location` fields and the current date:

1. If the current date is before `start_location`, the publication appears in the week containing `start_location`.
2. If the current date is after `end_location`, the publication appears in the week containing `end_location`.
3. If the current date is between `start_location` and `end_location`, the publication appears in the week containing the current date.

For convenience, only `start_displaying_on` must be set. If `start_location` is not set,
it defaults to the same value as `start_displaying_on`. If `end_location` is not set, it also defaults to the same value as `start_location` (if set, otherwise `start_displaying_on`).

This results in the following behavior:

- Only `start_displaying_on` set: the publication appears starting from that
  date, and always appears in the week containing `start_displaying_on`. (The
  current behavior.)
- Only `start_displaying_on` and `start_location` set: the publication appears
  starting from that date, and appears in the week containing `start_location`.
- Only `start_displaying_on` and `end_location` set: the publication appears
  starting from the `start_displaying_on` date in the week containing
  `start_displaying_on`, and then moves forward week by week until it reaches
  the week containing `end_location`, where it remains.
- `start_displaying_on` is set to a date after `start_location`, and
  `end_location` is not set: the publication appears starting from that date,
  and it appears in a week in the past.

As part of this change, we will get rid of the `metadata_key_for_released` field, since it is no longer needed. We will also change the idiom: instead of specifying a metadata key, users will specify explicit dates. This is more flexible, though users will need to make use of raw strings more often. For example, where we would before have written:

```yaml
metadata_key_for_released: released
```

We now write:

```yaml
start_displaying_on: !raw ${ publication.metadata.released }
```

----

# Determine display date in metadata

In this approach, the date that a publication starts appearing on the schedule is specified in the publication's metadata (usually in `publication.yaml`).

*Pros*

- Easier to specify special display times for individual publications
- Easier to implement: the schedule generator just reads the date from the publication metadata; we already do interpolation and templating there, so no need for special logic in the schedule generator.
- Self-contained: all information about a publication lives in one place
- Simpler mental model for users who just want to set dates without understanding templating

*Cons*

- Mixes content with presentation concerns - the publication metadata becomes coupled to how it will be displayed
- The materials metadata schema becomes dependent on the presentation layer
- Violates separation of concerns: the materials layer shouldn't need to know about website presentation


# Determine display date in schedule config

In this approach, the date that a publication starts appearing on the schedule is specified in the schedule configuration in a templated field. E.g., `start_displaying_on: !raw ${ publication.metadata.released }`.

*Pros*

- Separates content from presentation logic
- Reusability: same materials can be presented differently in different contexts without modifying publication files
- Collection-wide policies are easy to implement and change in one place
- Centralizes presentation logic - easier to understand how the schedule works by looking at schedule.yaml
- More DRY (Don't Repeat Yourself) - the logic for determining display dates is specified once per collection type
- Better for version control: changes to presentation logic show up as changes to one file, not scattered across many publication files
- Easier to maintain consistency across similar items
- Materials remain presentation-agnostic and more reusable

*Cons*

- Harder to implement: the schedule generator has to resolve the templated field for each publication when generating the schedule.
- The schedule config becomes more complex with template syntax
- Might be harder for non-technical users to understand template expressions
- Edge cases for individual publications might still require additional metadata fields or complex template logic
- Requires understanding of both the materials metadata schema and the template syntax

---


Start by resolving the primary and secondary content configs for each publication in each
activity type. This will turn `pimrary_content` into a list of lists; each inner list
contains the configs for the publications in that activity type.

Then create an Activity object for each publication in each activity type,
containing all the necessary information for rendering (title, link, due date,
etc.). Do the same for the "extra" primary and secondary content, if any.
Flatten the primary content activities into a single list, and the secondary
content activities into another single list, and append the extra activities to
the respective lists.

Map each activity to the appropriate week number based on the current date
and the `start_location` and `end_location` fields.


final result: two dicts, `primary_activities_by_week` and
`secondary_activities_by_week`, mapping week numbers to lists of activities to
display that week. Each activity is a dict with all the necessary information
for rendering (title, link, due date, etc.).




```
