import numpy as np
from typing import List, Dict

def perform_ipf(num_samples: int) -> List[Dict[str, str]]:
    """
    Performs Iterative Proportional Fitting to combine Israeli demographic statistics.
    """
    # Dimensions: Ethnicity (2), Religiosity (4), Origin (4), Income (3)
    # Marginals based on approximate Israeli demographics
    # Ethnicity: Jewish (0.79), Arab (0.21)
    m1 = np.array([0.79, 0.21])
    # Religiosity: Secular (0.45), Traditional (0.25), Religious (0.15), Ultra-Orthodox (0.15)
    m2 = np.array([0.45, 0.25, 0.15, 0.15])
    # Origin (mostly relevant for Jewish pop): Ashkenazi (0.3), Mizrahi (0.4), Sephardic (0.1), Mixed (0.2)
    m3 = np.array([0.3, 0.4, 0.1, 0.2])
    # Income: Low (0.3), Medium (0.5), High (0.2)
    m4 = np.array([0.3, 0.5, 0.2])

    # Initial seed matrix (all ones)
    seed = np.ones((2, 4, 4, 3))

    # IPF Loop
    for _ in range(20):
        # Update dimension 0
        current_m1 = seed.sum(axis=(1, 2, 3))
        seed = seed * (m1 / current_m1)[:, np.newaxis, np.newaxis, np.newaxis]

        # Update dimension 1
        current_m2 = seed.sum(axis=(0, 2, 3))
        seed = seed * (m2 / current_m2)[np.newaxis, :, np.newaxis, np.newaxis]

        # Update dimension 2
        current_m3 = seed.sum(axis=(0, 1, 3))
        seed = seed * (m3 / current_m3)[np.newaxis, np.newaxis, :, np.newaxis]

        # Update dimension 3
        current_m4 = seed.sum(axis=(0, 1, 2))
        seed = seed * (m4 / current_m4)[np.newaxis, np.newaxis, np.newaxis, :]

    # Normalize to probabilities
    prob_matrix = seed / seed.sum()

    # Generate samples based on the joint distribution
    flat_probs = prob_matrix.flatten()
    indices = np.random.choice(len(flat_probs), size=num_samples, p=flat_probs)

    ethnicity_labels = ['Jewish', 'Arab']
    religiosity_labels = ['Secular', 'Traditional', 'Religious', 'Ultra-Orthodox']
    origin_labels = ['Ashkenazi', 'Mizrahi', 'Sephardic', 'Mixed/Other']
    income_labels = ['Low', 'Medium', 'High']

    profiles = []
    for idx in indices:
        i1, i2, i3, i4 = np.unravel_index(idx, prob_matrix.shape)
        # Origin is generally tracked for the Jewish population in these categories
        origin_val = origin_labels[i3] if ethnicity_labels[i1] == 'Jewish' else 'N/A'
        profiles.append({
            "Ethnicity": ethnicity_labels[i1],
            "Religiosity": religiosity_labels[i2],
            "Origin": origin_val,
            "Income": income_labels[i4]
        })

    return profiles
