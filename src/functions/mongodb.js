import { MongoClient } from "mongodb";
import dotenv from "dotenv";

dotenv.config();

const DEFAULT_URI =
  "mongodb+srv://nikkivp15174_db_user:qcJuQoBvL8zyMTEb@cluster0.21r6h5c.mongodb.net/?appName=Cluster0";

let cachedClient;

function getClient() {
  if (cachedClient) return cachedClient;
  const uri = process.env.MONGODB_URI || DEFAULT_URI;
  cachedClient = new MongoClient(uri, { tlsAllowInvalidCertificates: shouldAllowInvalidCerts() });
  return cachedClient;
}

function shouldAllowInvalidCerts() {
  const value = process.env.MONGODB_TLS_ALLOW_INVALID_CERTS;
  if (!value) return false;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

function getUsersCollection() {
  const dbName = process.env.MONGODB_DB || "telegram_bot";
  return getClient().db(dbName).collection("users");
}

export async function saveUser(userId, username, firstName) {
  const client = getClient();
  await client.connect();
  const collection = getUsersCollection();
  await collection.updateOne(
    { user_id: userId },
    { $set: { user_id: userId, username, first_name: firstName } },
    { upsert: true }
  );
}

export async function getAllUserIds() {
  const client = getClient();
  await client.connect();
  const collection = getUsersCollection();
  const docs = await collection.find({}, { projection: { user_id: 1, _id: 0 } }).toArray();
  return docs.map((doc) => doc.user_id).filter((id) => typeof id === "number");
}
