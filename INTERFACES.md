# Automata CLI

This summary outlines the CLI's hybrid structure, providing both user-friendly top-level commands and more granular, nested commands for advanced control and debugging.

---

#### **1. Core Project Commands**

*   **`automata init`**: Set up a new course project.
*   **`automata build`**: Generate your course website and process materials.
    *   (Use `--from-existing-materials` to just build the website from pre-processed data).
*   **`automata calendar`**: Create an iCalendar file with course dates.
*   **`automata deploy`**: Build your project and publish it online.
*   **`automata preview`**: View your website locally with live updates as you make changes.
*   **`automata check`**: Verify all your project configurations are correct.

---

#### **2. Material Management (Top-Level Shortcuts with Nested Counterparts)**

*   **`automata status`**: See the current state of your materials and upcoming releases.
*   **`automata ready <PATH>`**: Mark materials in a directory as ready for publication. (Alias for `automata materials ready`).
*   **`automata unready <PATH>`**: Mark materials in a directory as not ready. (Alias for `automata materials unready`).

---

#### **3. Advanced Use & Debugging (Nested Commands)**

*   **`automata materials discover`**: Just find materials in your project.
*   **`automata materials build`**: Run processing recipes for materials.
*   **`automata materials export`**: Copy processed materials to the output folder.
*   **`automata materials ready <PATH>`**: Mark materials in a directory as ready for publication.
*   **`automata materials unready <PATH>`**: Mark materials in a directory as not ready.
*   **`automata materials resolve <FILE_PATH>`**: See the final, processed version of a YAML configuration file.

---
