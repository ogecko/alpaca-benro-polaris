import numpy as np

# Define the conversion function for csv floats
def convert_to_float(value):
    try:
        return float(value)
    except ValueError:
        return float('nan')

    
# Define the conversion function
def convert_to_arcsec(value):
    try: 
        value = float(value) % (360 * 3600)  # Normalize to 0-360 degrees in arc-seconds
        if value > 180 * 3600:
            value -= 360 * 3600  # Adjust to -180 to 180 degrees in arc-seconds
        elif value < -180 * 3600:
            value += 360 * 3600  # Adjust to -180 to 180 degrees in arc-seconds
        return value
    except ValueError:
        return float('nan')

# Define the conversion function
def convert_to_bool(value):
    try:
        return True if value=='True' else False
    except ValueError:
        return bool('nan')
    
# Define RMS calculation function
def rms(x):
    ac = x - x.mean()
    return np.sqrt(np.mean(np.square(ac)))
    
# Helper function for plotly scatter plots
def plot_formating(title, xtitle, ytitle):
    title={
        'text': title,
        'font': {
            'size': 24,  # Increase the font size
            'color': 'black',  # Set the font color
            'family': 'Arial',  # Set the font family
        },
        'x': 0.5,  # Center the title
        'xanchor': 'center'
    }
    labels={
        "x": xtitle,
        "y": ytitle
    }
    bgcolor = 'rgba(200, 200, 250, 0.5)'
    return title,labels,xtitle,ytitle,bgcolor
