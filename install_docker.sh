#!/bin/bash

# Update existing packages
sudo apt update && sudo apt upgrade -y

# Install necessary packages to allow apt to use a repository over HTTPS
sudo apt install apt-transport-https ca-certificates curl software-properties-common -y

# Add the official Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

# Add the Docker repository to APT sources
echo "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list

# Update the package database
sudo apt update

# Install Docker
sudo apt install docker-ce -y

# Start the Docker service
sudo systemctl start docker

# Enable Docker to start on boot
sudo systemctl enable docker

# Verify that Docker has been installed correctly
sudo docker --version

# Add the current user to the 'docker' group to avoid using 'sudo' with Docker
sudo usermod -aG docker $USER

# Final message
echo "Docker has been installed successfully. Please log out and log back in to apply the permission changes."