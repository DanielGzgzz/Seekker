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

    # Extended attribute pools
    professions = ['Software Engineer', 'Teacher', 'Doctor', 'Nurse', 'Business Owner', 'Retail Worker', 'Student', 'Unemployed', 'Retired', 'Lawyer', 'Accountant', 'Construction Worker', 'Artist']
    hobbies_pool = ['Reading', 'Gaming', 'Cooking', 'Traveling', 'Sports', 'Photography', 'Music', 'Gardening', 'Volunteering', 'Politics']
    political_views = ['Left-wing', 'Center-Left', 'Center', 'Center-Right', 'Right-wing', 'Non-political']
    asset_levels = ['None', 'Car', 'Apartment (Mortgaged)', 'Apartment (Owned)', 'Multiple Properties', 'Stock Portfolio']
    liability_levels = ['None', 'Student Debt', 'Credit Card Debt', 'Car Loan', 'Large Mortgage', 'Business Loan']

    profiles = []
    for idx in indices:
        i1, i2, i3, i4 = np.unravel_index(idx, prob_matrix.shape)

        eth = ethnicity_labels[i1]
        rel = religiosity_labels[i2]
        inc = income_labels[i4]

        # Origin is generally tracked for the Jewish population in these categories
        origin_val = origin_labels[i3] if eth == 'Jewish' else 'N/A'

        # Probabilistic assignments based on core traits
        age = int(np.random.normal(loc=38, scale=15))
        age = max(18, min(age, 85)) # Bound between 18 and 85

        # Adjust children based on religiosity and age
        base_children_mean = 2.0
        if rel == 'Ultra-Orthodox':
            base_children_mean = 5.0
        elif rel == 'Religious':
            base_children_mean = 3.5

        if age < 25:
            children = 0
        else:
            children = max(0, int(np.random.normal(loc=base_children_mean, scale=1.5)))

        # Adjust profession based on income and age
        if age > 67:
            profession = 'Retired'
        elif age < 23:
            profession = 'Student'
        else:
            if inc == 'High':
                prof_weights = [0.3, 0.05, 0.15, 0.05, 0.2, 0.0, 0.0, 0.0, 0.0, 0.15, 0.1, 0.0, 0.0]
            elif inc == 'Low':
                prof_weights = [0.0, 0.1, 0.0, 0.05, 0.05, 0.35, 0.1, 0.15, 0.0, 0.0, 0.0, 0.15, 0.05]
            else: # Medium
                prof_weights = [0.1, 0.2, 0.05, 0.1, 0.15, 0.15, 0.05, 0.05, 0.0, 0.05, 0.05, 0.0, 0.05]

            # Normalize just in case
            prof_weights = np.array(prof_weights) / sum(prof_weights)
            profession = np.random.choice(professions, p=prof_weights)

        # Assets & Liabilities based on age and income
        if inc == 'High' and age > 35:
            assets = np.random.choice(['Apartment (Owned)', 'Multiple Properties', 'Stock Portfolio'])
            liabilities = np.random.choice(['None', 'Business Loan'])
        elif inc == 'Low':
            assets = np.random.choice(['None', 'Car'])
            liabilities = np.random.choice(['Credit Card Debt', 'Car Loan', 'None'])
        else:
            assets = np.random.choice(['Car', 'Apartment (Mortgaged)'])
            liabilities = np.random.choice(['Large Mortgage', 'Student Debt', 'Car Loan'])

        # Political view based roughly on religiosity
        if rel in ['Ultra-Orthodox', 'Religious']:
            pol_weights = [0.0, 0.0, 0.05, 0.15, 0.7, 0.1]
        elif rel == 'Traditional':
            pol_weights = [0.05, 0.1, 0.3, 0.3, 0.15, 0.1]
        else: # Secular
            pol_weights = [0.25, 0.25, 0.3, 0.05, 0.05, 0.1]

        pol_weights = np.array(pol_weights) / sum(pol_weights)
        political_view = np.random.choice(political_views, p=pol_weights)

        # Random hobbies (pick 2 to 4)
        num_hobbies = np.random.randint(2, 5)
        hobbies = list(np.random.choice(hobbies_pool, size=num_hobbies, replace=False))

        profiles.append({
            "Ethnicity": eth,
            "Religiosity": rel,
            "Origin": origin_val,
            "Income": inc,
            "Age": age,
            "Profession": profession,
            "Children": children,
            "Assets": assets,
            "Liabilities": liabilities,
            "Political_Views": political_view,
            "Hobbies": hobbies
        })

    return profiles
