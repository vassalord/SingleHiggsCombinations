# coding: utf-8

"""
Hello World example task that extends DHI tasks.

This demonstrates how to import and extend tasks from the inference repository.
"""

import law
import luigi

from dhi.tasks.limits import PlotUpperLimits


class HelloWorld(PlotUpperLimits):
    """
    A simple hello world task that extends PlotUpperLimits from DHI.

    This task adds a custom printout before and after running the parent task,
    demonstrating how to extend existing DHI functionality.
    """

    task_namespace = "shi"

    custom_message = luigi.Parameter(
        default="Hello from Single Higgs Combinations!",
        description="a custom message to print; default: 'Hello from Single Higgs Combinations!'",
    )

    def __init__(self, *args, **kwargs):
        super(HelloWorld, self).__init__(*args, **kwargs)

        # Print initialization message
        print("\n" + "=" * 80)
        print("SHI HelloWorld Task Initialized!")
        print(f"Custom message: {self.custom_message}")
        print("This task extends: dhi.tasks.limits.PlotUpperLimits")
        print("=" * 80 + "\n")

    @law.decorator.log
    @law.decorator.notify
    def run(self):
        """
        Extended run method with custom printouts.
        """
        # Custom printout before running parent task
        self.publish_message("\n" + "=" * 80)
        self.publish_message(f">>> {self.custom_message}")
        self.publish_message(">>> Starting to create upper limit plot using DHI task...")
        self.publish_message(">>> Task parameters:")
        self.publish_message(f"    - POIs: {self.pois}")
        self.publish_message(f"    - Datacards: {len(self.datacards)} file(s)")
        self.publish_message(f"    - Scan parameters: {self.scan_parameters}")
        self.publish_message(f"    - Version: {self.version}")
        self.publish_message("=" * 80 + "\n")

        # Run the parent task (PlotUpperLimits)
        result = super(HelloWorld, self).run()

        # Custom printout after running parent task
        self.publish_message("\n" + "=" * 80)
        self.publish_message(">>> DHI task completed successfully!")
        self.publish_message(f">>> Output: {self.output().path}")
        self.publish_message(">>> SHI HelloWorld task finished!")
        self.publish_message("=" * 80 + "\n")

        return result
