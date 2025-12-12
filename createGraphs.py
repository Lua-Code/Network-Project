import pandas as pd
import matplotlib.pyplot as plt

# ===========================
#      Load the CSV
# ===========================
df = pd.read_csv("Telemetry_Results.csv")

data_packets = df[df['Message Type'] == 1]

# ===========================
#  Bytes per report vs interval
# ===========================
data_packets['reporting_interval'] = data_packets.groupby('Device_ID')['Timestamp'].diff()
data_packets['reporting_interval'].fillna(0, inplace=True)  

plt.figure(figsize=(10,6))
plt.scatter(data_packets['reporting_interval'], data_packets['Bytes Per Report'], alpha=0.6)
plt.xlabel("Reporting Interval (s)")
plt.ylabel("Bytes per Report")
plt.title("Bytes per Report vs Reporting Interval")
plt.grid(True)
plt.savefig("bytes_vs_interval.png")  
plt.show()  
plt.close()  


duplicate_rate = data_packets.groupby('Device_ID')['Duplicate Flag'].mean()

def compute_loss(group):
    expected = group['Sequence Number'].max() - group['Sequence Number'].min() + 1
    received = group.shape[0]
    return (expected - received) / expected

loss_rate = data_packets.groupby('Device_ID').apply(compute_loss)

plt.figure(figsize=(10,6))
plt.scatter(loss_rate, duplicate_rate, alpha=0.6)
plt.xlabel("Packet Loss Rate")
plt.ylabel("Duplicate Rate")
plt.title("Duplicate Rate vs Packet Loss Rate")
plt.grid(True)
plt.savefig("duplicate_vs_loss.png")  
plt.show()
plt.close()
