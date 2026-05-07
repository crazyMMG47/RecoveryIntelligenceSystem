"""Simple 3-panel GUI showing agent reasoning and orchestrator resolution."""
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
from src.hackathon_agent.orchestrator import Orchestrator
from src.hackathon_agent.schemas import OrchestratorInput
from src.hackathon_agent.demo_data import DEMO_CASE


class AgentDemoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RecoveryIQ — Agent Decision Flow")
        self.root.geometry("1400x800")
        self.orchestrator = None

        # Colors
        self.bg_color = "#f0f0f0"
        self.clinical_bg = "#e3f2fd"
        self.insurance_bg = "#f3e5f5"
        self.orchestrator_bg = "#e8f5e9"

        # Title
        title = tk.Label(
            root,
            text="RecoveryIQ — Multi-Agent Decision Flow",
            font=("Arial", 16, "bold"),
            bg=self.bg_color,
        )
        title.pack(fill=tk.X, padx=10, pady=10)

        # Control bar
        control_frame = tk.Frame(root, bg=self.bg_color)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        self.run_button = tk.Button(
            control_frame,
            text="▶ Run Pipeline",
            command=self.run_pipeline,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12, "bold"),
            padx=20,
            pady=8,
        )
        self.run_button.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            control_frame,
            text="Ready",
            font=("Arial", 10),
            bg=self.bg_color,
            fg="#666",
        )
        self.status_label.pack(side=tk.LEFT, padx=20)

        # Main content: 3-column layout
        main_frame = tk.Frame(root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── Column 1: Clinical Agent ──
        self.clinical_frame = self._make_panel(
            main_frame,
            "🏥 CLINICAL AGENT",
            self.clinical_bg,
            0,
        )

        # ── Column 2: Insurance Agent ──
        self.insurance_frame = self._make_panel(
            main_frame,
            "💰 INSURANCE AGENT",
            self.insurance_bg,
            1,
        )

        # ── Column 3: Orchestrator ──
        self.orchestrator_frame = self._make_panel(
            main_frame,
            "🤖 ORCHESTRATOR",
            self.orchestrator_bg,
            2,
        )

    def _make_panel(self, parent, title, bg_color, column):
        """Create a labeled text panel."""
        frame = tk.Frame(parent, bg=bg_color, relief=tk.SUNKEN, borderwidth=2)
        frame.grid(row=0, column=column, sticky="nsew", padx=5, pady=5)
        parent.grid_columnconfigure(column, weight=1)

        # Title
        title_label = tk.Label(
            frame,
            text=title,
            font=("Arial", 12, "bold"),
            bg=bg_color,
            fg="#333",
        )
        title_label.pack(fill=tk.X, padx=10, pady=8)

        # Separator
        sep = tk.Frame(frame, height=2, bg="#ccc")
        sep.pack(fill=tk.X, padx=10)

        # Text area
        text_widget = scrolledtext.ScrolledText(
            frame,
            font=("Courier", 9),
            bg="white",
            fg="#333",
            height=35,
            width=40,
            wrap=tk.WORD,
            padx=10,
            pady=10,
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        return text_widget

    def run_pipeline(self):
        """Run the pipeline in a background thread."""
        self.run_button.config(state=tk.DISABLED)
        self.status_label.config(text="Running...", fg="#ff9800")
        self.root.update()

        thread = threading.Thread(target=self._execute_pipeline)
        thread.start()

    def _execute_pipeline(self):
        """Execute the orchestrator pipeline."""
        try:
            # Initialize orchestrator if needed
            if self.orchestrator is None:
                self.orchestrator = Orchestrator.from_env()

            # Clear panels
            self.clinical_frame.delete("1.0", tk.END)
            self.insurance_frame.delete("1.0", tk.END)
            self.orchestrator_frame.delete("1.0", tk.END)

            # Step 1: Clinical Agent
            self._update_status("Running Clinical Agent...")
            self.clinical_frame.insert(tk.END, "INPUT:\n")
            self.clinical_frame.insert(tk.END, f"  • Patient: {DEMO_CASE.case_id}\n")
            self.clinical_frame.insert(tk.END, f"  • Notes: {len(DEMO_CASE.clinical_notes)} clinical notes\n")
            self.clinical_frame.insert(tk.END, f"  • PT Notes: {len(DEMO_CASE.pt_notes)} PT assessments\n")
            self.clinical_frame.insert(tk.END, f"  • Imaging: {len(DEMO_CASE.imaging)} studies\n")
            self.clinical_frame.insert(tk.END, "\n")

            clinical_output = self.orchestrator.clinical_agent.run(
                self.orchestrator.build_clinical_input(
                    "Is additional PT justified?",
                    DEMO_CASE,
                )
            )

            self.clinical_frame.insert(tk.END, "ANALYSIS:\n")
            self.clinical_frame.insert(
                tk.END,
                f"  • Decision: {clinical_output.decision.recommended_path.upper()}\n",
            )
            self.clinical_frame.insert(tk.END, f"  • Confidence: {clinical_output.confidence.upper()}\n")
            self.clinical_frame.insert(tk.END, f"  • Evidence found: {len(clinical_output.evidence)} items\n")
            self.clinical_frame.insert(tk.END, "\n")

            self.clinical_frame.insert(tk.END, "EVIDENCE:\n")
            for ev in clinical_output.evidence[:5]:  # Show top 5
                self.clinical_frame.insert(
                    tk.END,
                    f"  ✓ [{ev.strength.upper()}] {ev.statement}\n",
                )
            if len(clinical_output.evidence) > 5:
                self.clinical_frame.insert(tk.END, f"  ... and {len(clinical_output.evidence) - 5} more\n")
            self.clinical_frame.insert(tk.END, "\n")

            self.clinical_frame.insert(tk.END, "REQUIREMENTS:\n")
            for req in clinical_output.requirements:
                status_icon = "✓" if req.status == "satisfied" else "✗"
                self.clinical_frame.insert(
                    tk.END,
                    f"  {status_icon} {req.description} [{req.status.upper()}]\n",
                )

            self.root.after(100, lambda: self.clinical_frame.see(tk.END))

            # Step 2: Insurance Agent
            self._update_status("Running Insurance Agent...")
            self.insurance_frame.insert(tk.END, "INPUT:\n")
            self.insurance_frame.insert(tk.END, f"  • Clinical decision: {clinical_output.decision.recommended_path.upper()}\n")
            self.insurance_frame.insert(tk.END, f"  • Clinical evidence: {len(clinical_output.evidence)} items\n")
            self.insurance_frame.insert(tk.END, f"  • Searching policy rules...\n")
            self.insurance_frame.insert(tk.END, "\n")

            insurance_input = self.orchestrator.build_insurance_input(
                "Is additional PT justified?",
                clinical_output,
            )
            insurance_output = self.orchestrator.insurance_agent.run(insurance_input)

            self.insurance_frame.insert(tk.END, "ANALYSIS:\n")
            self.insurance_frame.insert(
                tk.END,
                f"  • Coverage Position: {insurance_output.decision.coverage_position.upper()}\n",
            )
            self.insurance_frame.insert(tk.END, f"  • Confidence: {insurance_output.confidence.upper()}\n")
            self.insurance_frame.insert(tk.END, f"  • Coverage Rules Matched: {len(insurance_output.coverage_rules)}\n")
            self.insurance_frame.insert(tk.END, "\n")

            if insurance_output.coverage_rules:
                self.insurance_frame.insert(tk.END, "COVERAGE RULES:\n")
                for rule in insurance_output.coverage_rules[:5]:
                    status = "✓ SATISFIED" if rule.satisfied_by else "✗ UNSATISFIED"
                    self.insurance_frame.insert(
                        tk.END,
                        f"  {status}: {rule.rule_text}\n",
                    )
                self.insurance_frame.insert(tk.END, "\n")

            if insurance_output.validation_errors:
                self.insurance_frame.insert(tk.END, "⚠️  DEGRADED MODE (fallback output):\n")
                for err in insurance_output.validation_errors:
                    self.insurance_frame.insert(tk.END, f"  • {err}\n")
                self.insurance_frame.insert(tk.END, "\n")

            self.insurance_frame.insert(tk.END, "REQUIREMENTS:\n")
            for req in insurance_output.requirements:
                status_icon = "✓" if req.status == "satisfied" else "✗"
                self.insurance_frame.insert(
                    tk.END,
                    f"  {status_icon} {req.description} [{req.status.upper()}]\n",
                )

            self.root.after(100, lambda: self.insurance_frame.see(tk.END))

            # Step 3: Orchestrator
            self._update_status("Running Orchestrator...")
            self.orchestrator_frame.insert(tk.END, "INPUT:\n")
            self.orchestrator_frame.insert(tk.END, f"  • Clinical: {clinical_output.decision.recommended_path.upper()}\n")
            self.orchestrator_frame.insert(tk.END, f"  • Insurance: {insurance_output.decision.coverage_position.upper()}\n")
            self.orchestrator_frame.insert(tk.END, f"  • Checking for conflicts...\n")
            self.orchestrator_frame.insert(tk.END, "\n")

            orchestrator_input = OrchestratorInput(
                user_question="Is additional PT justified?",
                clinical_output=clinical_output,
                insurance_output=insurance_output,
            )
            orchestrator_output = self.orchestrator.build_final_output(orchestrator_input)

            self.orchestrator_frame.insert(tk.END, "ANALYSIS:\n")
            self.orchestrator_frame.insert(
                tk.END,
                f"  • Case Readiness: {orchestrator_output.case_resolution.readiness.upper()}\n",
            )
            self.orchestrator_frame.insert(
                tk.END,
                f"  • Recommended Path: {orchestrator_output.case_resolution.recommended_path.upper()}\n",
            )
            self.orchestrator_frame.insert(
                tk.END,
                f"  • Human Review: {'REQUIRED' if orchestrator_output.case_resolution.requires_human_review else 'NOT NEEDED'}\n",
            )
            self.orchestrator_frame.insert(tk.END, "\n")

            if orchestrator_output.conflict_items:
                self.orchestrator_frame.insert(tk.END, "⚡ CONFLICTS DETECTED:\n")
                for conflict in orchestrator_output.conflict_items:
                    blocking = "🔴 BLOCKING" if conflict.blocking else "⚠️ INFORMATIONAL"
                    self.orchestrator_frame.insert(
                        tk.END,
                        f"  {blocking}: {conflict.conflict_type}\n",
                    )
                    self.orchestrator_frame.insert(tk.END, f"    Reason: {conflict.reason}\n")
                self.orchestrator_frame.insert(tk.END, "\n")
            else:
                self.orchestrator_frame.insert(tk.END, "✓ No conflicts detected\n\n")

            self.orchestrator_frame.insert(tk.END, "🚫 BLOCKING REQUIREMENTS:\n")
            if orchestrator_output.blocking_requirements:
                for req in orchestrator_output.blocking_requirements:
                    self.orchestrator_frame.insert(
                        tk.END,
                        f"  • {req.description}\n",
                    )
            else:
                self.orchestrator_frame.insert(tk.END, "  None\n")
            self.orchestrator_frame.insert(tk.END, "\n")

            self.orchestrator_frame.insert(tk.END, "📋 WORKFLOW STEPS:\n")
            for i, step in enumerate(orchestrator_output.recommended_workflow, 1):
                self.orchestrator_frame.insert(
                    tk.END,
                    f"  {i}. [{step.owner.upper()}] {step.action}\n",
                )

            self.root.after(100, lambda: self.orchestrator_frame.see(tk.END))

            self._update_status("✓ Complete", "#4CAF50")

        except Exception as exc:
            self.orchestrator_frame.insert(tk.END, f"ERROR: {exc}")
            self._update_status(f"Error: {exc}", "#f44336")
            messagebox.showerror("Error", f"Pipeline failed: {exc}")
        finally:
            self.run_button.config(state=tk.NORMAL)

    def _update_status(self, message, color="#ff9800"):
        """Update status label."""
        self.status_label.config(text=message, fg=color)
        self.root.update()


if __name__ == "__main__":
    root = tk.Tk()
    gui = AgentDemoGUI(root)
    root.mainloop()
