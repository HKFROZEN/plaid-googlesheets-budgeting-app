"""
Category styling utilities for personal finance categories.
Provides colors and emojis for different spending categories.
"""

def get_category_style(category):
    """Get color and emoji for a personal finance category"""
    if not category:
        return {'color': '#6c757d', 'emoji': '📋'}
    
    # Map common personal finance categories to colors and emojis
    category_styles = {
        # Food & Dining
        'FOOD_AND_DRINK': {'color': '#ff6b6b', 'emoji': '🍽️'},
        'GENERAL_MERCHANDISE': {'color': '#4ecdc4', 'emoji': '🛍️'},
        'GROCERIES': {'color': '#45b7d1', 'emoji': '🛒'},
        'RESTAURANTS': {'color': '#ff9f43', 'emoji': '🍕'},
        
        # Transportation
        'TRANSPORTATION': {'color': '#5f27cd', 'emoji': '🚗'},
        'GAS': {'color': '#00d2d3', 'emoji': '⛽'},
        'PARKING': {'color': '#ff6348', 'emoji': '🅿️'},
        'PUBLIC_TRANSPORTATION': {'color': '#3742fa', 'emoji': '🚌'},
        'TAXI': {'color': '#ffa502', 'emoji': '🚕'},
        
        # Entertainment
        'ENTERTAINMENT': {'color': '#e056fd', 'emoji': '🎬'},
        'RECREATION': {'color': '#ff3838', 'emoji': '🎮'},
        'STREAMING': {'color': '#8c7ae6', 'emoji': '📺'},
        'MUSIC': {'color': '#ff6b9d', 'emoji': '🎵'},
        
        # Shopping
        'RETAIL': {'color': '#6c5ce7', 'emoji': '🛒'},
        'CLOTHING': {'color': '#fd79a8', 'emoji': '👕'},
        'ELECTRONICS': {'color': '#0984e3', 'emoji': '💻'},
        'HOME_IMPROVEMENT': {'color': '#d63031', 'emoji': '🔨'},
        'SPORTING_GOODS': {'color': '#00b894', 'emoji': '⚽'},
        
        # Healthcare
        'HEALTHCARE': {'color': '#55a3ff', 'emoji': '🏥'},
        'MEDICAL': {'color': '#ff6b6b', 'emoji': '💊'},
        'DENTAL': {'color': '#74b9ff', 'emoji': '🦷'},
        'VETERINARY': {'color': '#fdcb6e', 'emoji': '🐕'},
        
        # Bills & Utilities
        'UTILITIES': {'color': '#00cec9', 'emoji': '💡'},
        'INTERNET': {'color': '#6c5ce7', 'emoji': '📡'},
        'MOBILE_PHONE': {'color': '#fd79a8', 'emoji': '📱'},
        'CABLE': {'color': '#fdcb6e', 'emoji': '📺'},
        
        # Financial
        'LOAN_PAYMENTS': {'color': '#e17055', 'emoji': '💳'},
        'CREDIT_CARD_PAYMENT': {'color': '#a29bfe', 'emoji': '💳'},
        'BANK_FEES': {'color': '#636e72', 'emoji': '🏦'},
        'ATM_FEES': {'color': '#b2bec3', 'emoji': '🏧'},
        
        # Income
        'PAYROLL': {'color': '#00b894', 'emoji': '💰'},
        'DEPOSIT': {'color': '#55a3ff', 'emoji': '💵'},
        'TRANSFER_IN': {'color': '#6c5ce7', 'emoji': '📈'},
        'REFUND': {'color': '#00cec9', 'emoji': '↩️'},
        
        # Travel
        'TRAVEL': {'color': '#ff7675', 'emoji': '✈️'},
        'HOTEL': {'color': '#fd79a8', 'emoji': '🏨'},
        'FLIGHTS': {'color': '#74b9ff', 'emoji': '✈️'},
        'CAR_RENTAL': {'color': '#fdcb6e', 'emoji': '🚗'},
        
        # Personal Care
        'PERSONAL_CARE': {'color': '#e84393', 'emoji': '💄'},
        'BEAUTY': {'color': '#fd79a8', 'emoji': '💅'},
        'HAIR': {'color': '#ff6b9d', 'emoji': '💇'},
        
        # Education
        'EDUCATION': {'color': '#0984e3', 'emoji': '📚'},
        'STUDENT_LOAN': {'color': '#74b9ff', 'emoji': '🎓'},
        'TUITION': {'color': '#6c5ce7', 'emoji': '🏫'},
        
        # Other
        'OTHER': {'color': '#6c757d', 'emoji': '📋'},
        'GENERAL': {'color': '#6c757d', 'emoji': '📋'},
        'MISC': {'color': '#6c757d', 'emoji': '📋'},
    }
    
    # Get style for category, default to gray if not found
    return category_styles.get(category.upper(), {'color': '#6c757d', 'emoji': '📋'}) 