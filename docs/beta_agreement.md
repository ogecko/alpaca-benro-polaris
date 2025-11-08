[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)
# Alpha and Beta Testing Agreement

Please review the following agreement before using any Alpha or Beta version of this software.

## You agree to the following responsibilities

### 1. Create a GitHub account
If you don’t already have a GitHub account, please create one and let me know so I can add you to the repository. This will allow you to raise issues and contribute directly to the beta test results document.


---

### 2. Document your test environment

Can you please let me know the details about the equipment you are testing with. Include details on 
* Hardware: MiniPC model, Tablet model, Phone model. 
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc
* Platform: OS Version, Application Versions (Nina/Stellarium, etc), Browser Version, etc. 

If you know Markdown you can add this directly to your section of the following document
https://github.com/ogecko/alpaca-benro-polaris/blob/dev2_0/docs/beta_results_v2.md 

Otherwise, just send me a note on Discord and I’ll add it for you.


---

### 3. Perform a range of test cases
Break down your assessment into a series of tests with clear goals and expected outcomes. Take small steps, confirming each along the way. Include real-world use cases, as well as load and performance tests where possible.

Example of tests may be
* Install and connect V2 driver to Polaris, confirming communications
* Use Pilot App Connection Page to connect to Polaris without using BP App
* Use Pilot App Settings Page to set lat/lon of the Driver
* Use Single Point Alignment to confirm it operates the same as in V1
* Connect Stellarium Desktop to V2 Driver via ASCOM
* Confirm GOTO and SYNC are possible through Stellarium
* Connect Nina Telescope to V2 Driver via Alpaca
* Connect Nina Rotator to V2 Driver via AAlpaca
* Confirm PARK, Home functions work from Nina
* Confirm Pulse-guiding with PHD2
* Confirm Mosaics with Nina
* etc


---

### 4. Keep a clear record of the tests you perform and their outcomes.
Document the purpose of the test, how you performed the test, what was expected, what actually happened, what troublehsooting or diagnostics you have performed if it didnt work.

---

### 5. Report any issues by creating GitHub issues with relevant details.
Before raising a formal issue, please check that it hasn’t already been reported.  If you're unsure whether to raise an issue, feel free to discuss it on Discord first. Use the GitHub issue template to include the necessary information.

---

### 6. Reproduce, Isolate and Diagnose the cause.
To help resolve issues effectively, follow these steps:

* **Reproduce** - If something goes wrong, try to repeat it and record the steps. This is especially important for intermittent problems.  

* **Isolate** - Try to narrow down the cause or area of the problem. The more constrained the issue, the easier it is to resolve. Repeat the test under different scenarios to help isolate any special causes. 


* **Diagnose** - Compare what is expected vs what was observed. What might be causing the problem. What data/logs might be needed to help find the cause. Anything you can do before involving someone else?

---

### 7. Review the documentation and videos

Spend time reading the documentation and watching the videos.  Highlight any unfamiliar terms, unclear sections, or outdated content.  Make suggestions to improve clarity or completeness.

---

### 8. Summarise results by **30 November**

Confirm that you will submit a final summary of your Beta testing feedback by 30 November, to allow time for fixes before release. Keep notes throughout the testing period and summarise your experience at the end.

---


### 9. Confirm that you will not share any pre-release material or opinions
The pre-release materials may change significantly before release and may not reflect final outcomes. Please keep communications within the Beta test team.

### 10. Maintain constructive and respectful communication.

This is a collaborative effort by volunteers, and everyone’s input is valued. Please keep feedback focused, detailed, and solution-oriented; even when things go wrong. Frustration is understandable, but comments should aim to help diagnose and improve the system. If expectations aren’t being met or the process isn’t working for you, it’s okay to step back. We’re all pushing the limits of what Polaris can do, and thoughtful input is what helps us move forward.

## Additional Notes

* You may be asked to test specific features or edge cases as development progresses.
* Feedback on usability, performance, and reliability is especially valuable.
* If you encounter blocking bugs or regressions, please flag them with priority in your GitHub issue.
* All feedback, even small observations, helps improve the final release.

Thank you for helping shape the future of this project.
