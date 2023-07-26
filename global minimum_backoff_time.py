global minimum_backoff_time
global MAXIMUM_BACKOFF_TIME

# Publish to the events or state topic based on the flag.
sub_topic = "events" if args.message_type == "event" else "state"

mqtt_topic = f"/devices/{args.device_id}/{sub_topic}"

jwt_iat = datetime.datetime.now(tz=datetime.timezone.utc)
jwt_exp_mins = args.jwt_expires_minutes
client = get_client(
    args.project_id,
    args.cloud_region,
    args.registry_id,
    args.device_id,
    args.private_key_file,
    args.algorithm,
    args.ca_certs,
    args.mqtt_bridge_hostname,
    args.mqtt_bridge_port,
)

# Publish num_messages messages to the MQTT bridge once per second.
for i in range(1, args.num_messages + 1):
    # Process network events.
    client.loop()

    # Wait if backoff is required.
    if should_backoff:
        # If backoff time is too large, give up.
        if minimum_backoff_time > MAXIMUM_BACKOFF_TIME:
            print("Exceeded maximum backoff time. Giving up.")
            break

        # Otherwise, wait and connect again.
        delay = minimum_backoff_time + random.randint(0, 1000) / 1000.0
        print(f"Waiting for {delay} before reconnecting.")
        time.sleep(delay)
        minimum_backoff_time *= 2
        client.connect(args.mqtt_bridge_hostname, args.mqtt_bridge_port)

    payload = f"{args.registry_id}/{args.device_id}-payload-{i}"
    print(f"Publishing message {i}/{args.num_messages}: '{payload}'")
    seconds_since_issue = (
        datetime.datetime.now(tz=datetime.timezone.utc) - jwt_iat
    ).seconds
    if seconds_since_issue > 60 * jwt_exp_mins:
        print(f"Refreshing token after {seconds_since_issue}s")
        jwt_iat = datetime.datetime.now(tz=datetime.timezone.utc)
        client.loop()
        client.disconnect()
        client = get_client(
            args.project_id,
            args.cloud_region,
            args.registry_id,
            args.device_id,
            args.private_key_file,
            args.algorithm,
            args.ca_certs,
            args.mqtt_bridge_hostname,
            args.mqtt_bridge_port,
        )
    # Publish "payload" to the MQTT topic. qos=1 means at least once
    # delivery. Cloud IoT Core also supports qos=0 for at most once
    # delivery.
    client.publish(mqtt_topic, payload, qos=1)

    # Send events every second. State should not be updated as often
    for i in range(0, 60):
        time.sleep(1)
        client.loop()