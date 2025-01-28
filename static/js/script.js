document.addEventListener("DOMContentLoaded", function() {
  // File Upload Handling
  document.getElementById('fileInput').addEventListener('change', function() {
    const fileInput = this;
    const selectedFileName = document.getElementById('selectedFileName');

    if (fileInput.files.length > 0) {
      selectedFileName.textContent = `Selected file: ${fileInput.files[0].name}`;
      selectedFileName.classList.remove('hidden');
    } else {
      selectedFileName.classList.add('hidden');
    }
  });

  const uploadForm = document.getElementById("uploadForm");
  const fileInput = document.getElementById("fileInput");
  const analyzeBtn = document.getElementById("analyzeBtn");
  const progressBar = document.getElementById("progressBar");
  const progressBarFill = document.getElementById("progressBarFill");
  const loadingSpinner = document.getElementById("loadingSpinner");
  const resultsSection = document.getElementById("resultsSection");
  const problemsTab = document.getElementById("problemsTab");
  const solutionsTab = document.getElementById("solutionsTab");
  const problemsContent = document.getElementById("problemsContent");
  const solutionsContent = document.getElementById("solutionsContent");
  const problemsList = document.getElementById("problemsList");
  const solutionsList = document.getElementById("solutionsList");
  const downloadPdfBtn = document.getElementById("downloadPdfBtn");

  const toggleTab = (activeTab, inactiveTab, activeContent, inactiveContent) => {
    activeTab.classList.add("bg-blue-600", "text-white");
    activeTab.classList.remove("bg-gray-300", "text-gray-700");
    inactiveTab.classList.add("bg-gray-300", "text-gray-700");
    inactiveTab.classList.remove("bg-blue-600", "text-white");
    activeContent.classList.remove("hidden");
    inactiveContent.classList.add("hidden");
  };

  problemsTab.addEventListener("click", () => {
    toggleTab(problemsTab, solutionsTab, problemsContent, solutionsContent);
  });

  solutionsTab.addEventListener("click", () => {
    toggleTab(solutionsTab, problemsTab, solutionsContent, problemsContent);
  });

  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
      Swal.fire("Error", "Please select a file before uploading.", "error");
      return;
    }

    // Show progress bar and spinner
    progressBar.classList.remove("hidden");
    loadingSpinner.classList.remove("hidden");
    progressBarFill.style.width = "0%";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();
      const { problems, solutions } = result;

      // Populate Problems Tab
      problemsList.innerHTML = "";
      problems.forEach((problem) => {
        const listItem = document.createElement("li");
        listItem.textContent = problem;
        problemsList.appendChild(listItem);
      });

      // Populate Solutions Tab
      solutionsList.innerHTML = "";
      solutions.forEach((solution) => {
        const listItem = document.createElement("li");
        listItem.innerHTML = solution; // Assuming solutions are in LaTeX and rendered with MathJax
        solutionsList.appendChild(listItem);
      });

      // Show results section and default to Problems tab
      resultsSection.classList.remove("hidden");
      toggleTab(problemsTab, solutionsTab, problemsContent, solutionsContent);

      // Rerender MathJax for LaTeX
      if (window.MathJax) {
        MathJax.typesetPromise();
      }

      // Show success message with SweetAlert
      Swal.fire({
        icon: 'success',
        title: 'Upload Complete',
        text: 'Your file has been successfully uploaded and analyzed. View the results below.',
        confirmButtonText: 'View Results'
      });

    } catch (error) {
      Swal.fire("Error", error.message, "error");
    } finally {
      progressBar.classList.add("hidden");
      loadingSpinner.classList.add("hidden");
    }
  });

  fileInput.addEventListener("change", () => {
    const selectedFileName = document.getElementById("selectedFileName");
    selectedFileName.textContent = fileInput.files[0]?.name || "";
    selectedFileName.classList.remove("hidden");
  });
  downloadPdfBtn.addEventListener("click", () => {
    const solutions = Array.from(document.querySelectorAll('#solutionsList li')).map(li => li.textContent);

    fetch('/download-solutions-pdf', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ solutions })
    })
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.blob();
      })
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'solutions.pdf';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(error => {
        console.error("Error downloading PDF:", error);
        Swal.fire("Error", "Failed to download PDF.", "error");
      });
  });

  // Hamburger Button and Dropdown Menu Handling
  const hamburgerBtn = document.getElementById('hamburgerBtn');
  const dropdownMenu = document.getElementById('dropdownMenu');

  hamburgerBtn.addEventListener('click', function() {
    dropdownMenu.classList.toggle('hidden');
  });

  // Upgrade Modal Handling
  const upgradeModal = document.getElementById('upgradeModal');
  const payButton = document.getElementById('payButton');
  const closeUpgradeModal = document.getElementById('closeUpgradeModal');
  const upgradeBtn = document.getElementById('upgradeBtn');
  const upgradeBtnMobile = document.getElementById('upgradeBtnMobile');

  // Show the upgrade modal when the upgrade button is clicked
  const showUpgradeModal = () => {
    upgradeModal.classList.remove('hidden');
  };

  upgradeBtn.addEventListener('click', showUpgradeModal);
  upgradeBtnMobile.addEventListener('click', showUpgradeModal);

  // Hide the upgrade modal when the cancel button is clicked
  closeUpgradeModal.addEventListener('click', function() {
    upgradeModal.classList.add('hidden');
  });

  // Handle payment with Flutterwave
  payButton.addEventListener('click', function() {
    FlutterwaveCheckout({
      public_key: "FLWPUBK_TEST-37b846170fffb98f956aac39e97791bf-X",
      tx_ref: "RX1_" + Date.now(),
      amount: 4500,
      currency: "NGN",
      payment_options: "card, banktransfer, ussd",
      customer: {
        email: "igatajohn15@gmail.com",
        phonenumber: "08126159242",
        name: "Igata John",
      },
      callback: function (data) { // specified callback function
        console.log(data);
        if (data.status === "successful") {
          Swal.fire("Success", "Your account has been upgraded!", "success");
          upgradeModal.classList.add('hidden');

          // Make a POST request to your backend to confirm the upgrade
          fetch('/confirm-upgrade', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tx_ref: data.tx_ref })
          })
          .then(response => response.json())
          .then(responseData => {
            if (responseData.success) {
              console.log("Upgrade confirmed.");
            } else {
              console.error("Error confirming upgrade: ", responseData.message);
            }
          })
          .catch(error => {
            console.error("Error confirming upgrade: ", error);
          });
        } else {
          Swal.fire("Error", "Payment failed. Please try again.", "error");
        }
      },
      customizations: {
        title: "QIT Solutions",
        description: "Payment for account upgrade",
        logo: "/static/assets/qitlogo.png",
      },
    });
  });

  // Handle upload response
  function handleUploadResponse(response) {
    if (response.status === 403) {
      Swal.fire("Upgrade Required", response.error, "warning");
      upgradeModal.classList.remove('hidden');
    } else if (response.status === 200) {
      // Handle successful upload
    } else {
      // Handle other errors
    }
  }
});

// Modal Controls
document.getElementById('closeModal').addEventListener('click', function() {
  const modal = document.getElementById('conceptsModal');
  modal.classList.add('hidden');
});

document.getElementById('upgradeBtn').addEventListener('click', function() {
  const modal = document.getElementById('upgradeModal');
  modal.classList.remove('hidden');
});

document.getElementById('closeUpgradeModal').addEventListener('click', function() {
  const modal = document.getElementById('upgradeModal');
  modal.classList.add('hidden');
});
